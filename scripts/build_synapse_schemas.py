#!/usr/bin/env python3
"""Build flattened, Synapse-registrable JSON Schemas from the LinkML source.

Synapse does not support the full JSON Schema spec — internal ``$defs`` and the
``$ref`` pointers into them are rejected — so the LinkML output has to be
dereferenced before it can be registered. Every reference is resolved in place
and the ``$defs`` block is dropped, which in particular means enums land
directly on the property that uses them as an inline ``enum`` list.

The nullable unions LinkML emits for optional slots are collapsed for the same
reason: Synapse rejects an array-valued ``type``. ``--keep-nullable`` opts out,
but the result is not registrable.

``--validate`` submits each result to Synapse as a dry run, which is the only
way to confirm the output is actually registrable rather than merely valid JSON
Schema. It creates nothing.

Conventions here follow the sibling repos that already register schemas with
Synapse: nf-metadata-dictionary (utils/gen-json-schema-class.py) and
amp-als/data-model (Makefile). Registration itself is out of scope — this script
only writes files.

Usage:
    python scripts/build_synapse_schemas.py
    python scripts/build_synapse_schemas.py --version 1.0.0
    python scripts/build_synapse_schemas.py --class Portal
    python scripts/build_synapse_schemas.py --validate
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from linkml_runtime import SchemaView

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO_ROOT / "src" / "sage_cdm.yaml"
DEFAULT_OUT_DIR = REPO_ROOT / "dist" / "synapse"

#: Synapse namespaces every schema under an organization, embedded in the $id.
#: Override with --org; the organization must already exist in Synapse.
DEFAULT_ORG = "org.synapse.sagecdm"

REGISTRY_BASE = "https://repo-prod.prod.sagebase.org/repo/v1/schema/type/registered"
DRAFT_07 = "http://json-schema.org/draft-07/schema#"

#: Stripped from the root object: LinkML bookkeeping that Synapse has no use for.
ROOT_KEYS_TO_DROP = ("metamodel_version", "version")


def _display(path: Path) -> str:
    """Repo-relative where possible; an out-dir outside the repo is still legal."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


class CircularReferenceError(RuntimeError):
    """A ``$ref`` cycle that cannot be represented once flattened."""


def entity_classes(view: SchemaView) -> list[str]:
    """The classes that get their own registrable schema.

    An entity is anything descending from ``BaseEntity``. That deliberately
    excludes the abstract base itself, ``ProvenanceMixin`` (a mixin, whose slots
    are already materialized into its consumers), ``Portfolio`` (a multi-record
    container, not a thing Synapse binds to), and ``PersonIdentifier`` (an
    inlined structure that only ever appears nested inside PERSON).
    """
    return sorted(
        name
        for name in view.all_classes()
        if name != "BaseEntity" and "BaseEntity" in view.class_ancestors(name)
    )


def generate(schema_path: Path, class_name: str) -> dict:
    """Run LinkML's JSON Schema generator with ``class_name`` as the root."""
    result = subprocess.run(
        [
            "gen-json-schema",
            "--top-class", class_name,
            "--no-metadata",
            "--not-closed",
            str(schema_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(result.stdout)


def flatten(node, defs: dict, stack: frozenset = frozenset()):
    """Resolve every ``#/$defs/...`` pointer in ``node`` into its target.

    Sibling keywords on the referring object win over the target's. LinkML emits
    the per-slot description alongside the ``$ref`` (the slot's own wording from
    the Confluence spec), while the target carries the enum's or class's generic
    description — so a naive "replace the whole object" dereference would
    silently discard the more specific text. Merging keeps it.
    """
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/$defs/"):
                raise ValueError(f"unsupported non-local reference: {ref!r}")
            name = ref.rsplit("/", 1)[-1]
            if name in stack:
                raise CircularReferenceError(
                    f"circular reference through {name!r}; cannot be flattened "
                    f"(cycle: {' -> '.join([*stack, name])})"
                )
            if name not in defs:
                raise KeyError(f"dangling reference: {ref!r}")
            merged = flatten(defs[name], defs, stack | {name})
            if not isinstance(merged, dict):
                return merged
            for key, value in node.items():
                if key != "$ref":
                    merged[key] = value
            return merged
        return {key: flatten(value, defs, stack) for key, value in node.items()}
    if isinstance(node, list):
        return [flatten(item, defs, stack) for item in node]
    return node


def collapse_nullable(node):
    """Rewrite ``type: [X, "null"]`` as ``type: X``.

    LinkML marks every optional slot nullable. That is valid draft-07, but
    Synapse rejects an array-valued ``type`` outright, confirmed by dry run:

        No enum constant
        org.sagebionetworks.schema.Type.["string","null"]

    Collapsing is safe for Synapse annotations, where an unset value is an
    absent key rather than an explicit null, and ``required`` already governs
    presence.

    On by default, and required for registration -- ``--keep-nullable`` opts out
    but produces schemas Synapse will not accept.
    """
    if isinstance(node, dict):
        kind = node.get("type")
        if isinstance(kind, list):
            concrete = [t for t in kind if t != "null"]
            if len(concrete) == 1:
                node = {**node, "type": concrete[0]}
        return {key: collapse_nullable(value) for key, value in node.items()}
    if isinstance(node, list):
        return [collapse_nullable(item) for item in node]
    return node


def strip_boolean_additional_properties(node):
    """Drop every boolean ``additionalProperties``, at any depth.

    Draft-07 allows it to be either a boolean or a schema, but Synapse's parser
    only accepts a schema and rejects the whole document otherwise:

        JSONObjectAdapterException: JSONObject["additionalProperties"]
        is not a JSONObject

    LinkML emits ``false`` on every inlined class (PERSON's identifiers) and
    ``--not-closed`` puts ``true`` on the root, so both forms show up. Dropping
    the keyword restores the draft-07 default, which is the same permissive
    behaviour ``true`` was asking for. The ``false`` case does loosen the nested
    objects, but Synapse would not have honoured it either way.
    """
    if isinstance(node, dict):
        return {
            key: strip_boolean_additional_properties(value)
            for key, value in node.items()
            if not (key == "additionalProperties" and isinstance(value, bool))
        }
    if isinstance(node, list):
        return [strip_boolean_additional_properties(item) for item in node]
    return node


def to_synapse(raw: dict, class_name: str, org: str, version: str | None,
               collapse_nulls: bool = True) -> dict:
    """Flatten ``raw`` and apply the Synapse registration conventions."""
    defs = raw.get("$defs", {})
    schema = {key: value for key, value in raw.items() if key != "$defs"}
    schema = flatten(schema, defs)
    if collapse_nulls:
        schema = collapse_nullable(schema)
    schema = strip_boolean_additional_properties(schema)

    suffix = f"-{version}" if version else ""
    schema["$id"] = f"{REGISTRY_BASE}/{org}-{class_name.lower()}{suffix}"
    schema["$schema"] = DRAFT_07
    schema["title"] = class_name

    for key in ROOT_KEYS_TO_DROP:
        schema.pop(key, None)

    # Property titles echo the property name, matching the registered schemas in
    # nf-metadata-dictionary; the curator UI surfaces this as the field label.
    for prop_name, prop_schema in schema.get("properties", {}).items():
        if isinstance(prop_schema, dict):
            prop_schema["title"] = prop_name

    return schema


#: Synapse validates schema creation asynchronously: POST returns a token, then
#: the job is polled until it settles.
CREATE_ASYNC_START = "/schema/type/create/async/start"
JOB_STATUS = "/asynchronous/job/{token}"


def _login():
    """Authenticate, preferring the env var and falling back to ~/.synapseConfig."""
    import synapseclient

    syn = synapseclient.Synapse(silent=True)
    token = os.environ.get("SYNAPSE_AUTH_TOKEN")
    if token:
        syn.login(authToken=token)
    else:
        syn.login()
    return syn


def validate_with_synapse(paths: list[Path], timeout: float = 300.0) -> int:
    """Dry-run each schema against Synapse; return the number that failed.

    ``dryRun`` asks Synapse to run the same validation it would on a real
    create, without registering anything. This is what catches the parts of the
    JSON Schema spec Synapse does not implement — a schema can be perfectly
    valid draft-07 and still be rejected here, which is the whole reason this
    build flattens.
    """
    try:
        syn = _login()
    except Exception as exc:  # noqa: BLE001 - surface any auth failure verbatim
        print(f"error: could not log in to Synapse: {exc}\n"
              f"       set SYNAPSE_AUTH_TOKEN or configure ~/.synapseConfig",
              file=sys.stderr)
        return len(paths)

    pending: dict[str, Path] = {}
    failed = 0

    for path in paths:
        body = json.dumps({"schema": json.loads(path.read_text()), "dryRun": True})
        try:
            pending[syn.restPOST(CREATE_ASYNC_START, body)["token"]] = path
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {path.name}: could not start validation: {exc}",
                  file=sys.stderr)
            failed += 1

    deadline = time.monotonic() + timeout
    while pending:
        if time.monotonic() > deadline:
            for path in pending.values():
                print(f"  FAIL {path.name}: validation did not settle within "
                      f"{timeout:.0f}s", file=sys.stderr)
                failed += 1
            break
        for token, path in list(pending.items()):
            try:
                status = syn.restGET(JOB_STATUS.format(token=token))
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {path.name}: {exc}", file=sys.stderr)
                failed += 1
                del pending[token]
                continue
            if status["jobState"] == "PROCESSING":
                continue
            del pending[token]
            if status["jobState"] == "FAILED":
                print(f"  FAIL {path.name}: {status.get('errorMessage')}",
                      file=sys.stderr)
                failed += 1
            else:
                print(f"  ok   {path.name} accepted by Synapse")
        if pending:
            time.sleep(2)

    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA,
                        help=f"LinkML entry point (default: {_display(DEFAULT_SCHEMA)})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help=f"output directory (default: {_display(DEFAULT_OUT_DIR)})")
    parser.add_argument("--org", default=DEFAULT_ORG,
                        help=f"Synapse organization prefix for $id (default: {DEFAULT_ORG})")
    parser.add_argument("--version", default=None,
                        help="semantic version to append to the registered $id (e.g. 1.0.0)")
    parser.add_argument("--keep-nullable", dest="collapse_nullable",
                        action="store_false",
                        help="keep LinkML's type: [X, 'null'] unions instead of "
                             "collapsing them to type: X. Synapse rejects these, "
                             "so the output will not register.")
    parser.add_argument("--validate", action="store_true",
                        help="dry-run each schema against the Synapse API; needs "
                             "SYNAPSE_AUTH_TOKEN or ~/.synapseConfig. Registers "
                             "nothing.")
    parser.add_argument("--class", dest="class_name", default=None,
                        help="build a single class instead of every entity")
    args = parser.parse_args()

    if not args.schema.exists():
        print(f"error: schema not found: {args.schema}", file=sys.stderr)
        return 1

    view = SchemaView(str(args.schema))
    classes = entity_classes(view)

    if args.class_name:
        if args.class_name not in classes:
            print(f"error: {args.class_name!r} is not an entity class. "
                  f"Available: {', '.join(classes)}", file=sys.stderr)
            return 1
        classes = [args.class_name]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0

    for class_name in classes:
        try:
            schema = to_synapse(generate(args.schema, class_name), class_name,
                                args.org, args.version, args.collapse_nullable)
        except subprocess.CalledProcessError as exc:
            print(f"  FAIL {class_name}: gen-json-schema exited {exc.returncode}\n"
                  f"       {exc.stderr.strip()}", file=sys.stderr)
            failed += 1
            continue
        except (CircularReferenceError, KeyError, ValueError) as exc:
            print(f"  FAIL {class_name}: {exc}", file=sys.stderr)
            failed += 1
            continue

        out_path = args.out_dir / f"{class_name}.json"
        out_path.write_text(json.dumps(schema, indent=2) + "\n")
        n_props = len(schema.get("properties", {}))
        n_enums = sum(
            1 for p in schema.get("properties", {}).values()
            if isinstance(p, dict) and "enum" in p
        )
        print(f"  ok   {_display(out_path)} "
              f"({n_props} properties, {n_enums} inline enum(s), "
              f"{out_path.stat().st_size:,} bytes)")

    if failed:
        print(f"\n{failed} schema(s) failed to build", file=sys.stderr)
        return 1
    print(f"\nWrote {len(classes)} schema(s) to {_display(args.out_dir)}")

    if args.validate:
        written = [args.out_dir / f"{name}.json" for name in classes]
        print(f"\nValidating {len(written)} schema(s) against Synapse (dry run)...")
        rejected = validate_with_synapse(written)
        if rejected:
            print(f"\n{rejected} schema(s) rejected by Synapse", file=sys.stderr)
            return 1
        print(f"\nAll {len(written)} schema(s) accepted by Synapse")

    return 0


if __name__ == "__main__":
    sys.exit(main())
