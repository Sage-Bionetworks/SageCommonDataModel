"""The Synapse-facing JSON Schemas are flat and still describe the same model.

Synapse rejects the full JSON Schema spec — internal ``$defs`` and the ``$ref``
pointers into them in particular — so `scripts/build_synapse_schemas.py`
dereferences LinkML's output before it can be registered. Flattening is exactly
the kind of transform that can quietly lose information, so these tests check
both halves: that the output really is flat, and that it still accepts and
rejects the same instances the source schema does.

The schemas are built into a tmp directory rather than read from dist/, so the
suite does not depend on a prior build step having run.
"""

import json
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from conftest import ENTITY_CLASSES, EXAMPLES, REPO_ROOT, load_yaml

SCRIPT = REPO_ROOT / "scripts" / "build_synapse_schemas.py"
DRAFT_07 = "http://json-schema.org/draft-07/schema#"


@pytest.fixture(scope="module")
def synapse_schemas(tmp_path_factory):
    """Build every entity schema once, and hand back {class name: schema}."""
    out_dir = tmp_path_factory.mktemp("synapse")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out-dir", str(out_dir)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"build failed:\n{result.stdout}\n{result.stderr}"
    return {p.stem: json.loads(p.read_text()) for p in out_dir.glob("*.json")}


@lru_cache(maxsize=None)
def _build(class_name):
    """Build one entity schema with default options, into a throwaway directory."""
    out_dir = Path(tempfile.mkdtemp())
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--class", class_name, "--out-dir", str(out_dir)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"build failed:\n{result.stdout}\n{result.stderr}"
    return json.loads((out_dir / f"{class_name}.json").read_text())


def _walk(node):
    """Every (key, value) pair anywhere in the document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def test_every_entity_gets_a_schema(synapse_schemas):
    assert set(synapse_schemas) == set(ENTITY_CLASSES)


def test_container_and_abstract_classes_are_not_registered(synapse_schemas):
    """Portfolio is a document container and PersonIdentifier only ever appears
    nested; neither is something Synapse binds to."""
    for name in ("Portfolio", "BaseEntity", "ProvenanceMixin", "PersonIdentifier"):
        assert name not in synapse_schemas


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_schema_is_flat(class_name, synapse_schemas):
    """No $ref and no $defs survive anywhere — the whole point of the build."""
    keys = [key for key, _ in _walk(synapse_schemas[class_name])]
    assert "$ref" not in keys, "Synapse cannot resolve $ref"
    assert "$defs" not in keys and "definitions" not in keys


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_schema_is_valid_draft_07(class_name, synapse_schemas):
    schema = synapse_schemas[class_name]
    assert schema["$schema"] == DRAFT_07
    Draft7Validator.check_schema(schema)


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_registered_id_follows_the_synapse_convention(class_name, synapse_schemas):
    """Matches the pattern used by nf-metadata-dictionary and amp-als."""
    schema = synapse_schemas[class_name]
    assert schema["$id"] == (
        "https://repo-prod.prod.sagebase.org/repo/v1/schema/type/registered/"
        f"org.synapse.sagecdm-{class_name.lower()}"
    )
    assert schema["title"] == class_name


@pytest.mark.parametrize("class_name,filename", sorted(ENTITY_CLASSES.items()))
def test_example_still_validates_after_flattening(class_name, filename, synapse_schemas):
    validator = Draft7Validator(synapse_schemas[class_name])
    errors = [e.message for e in validator.iter_errors(load_yaml(EXAMPLES / filename))]
    assert not errors, "\n".join(errors)


def test_enums_are_inlined_on_the_property(synapse_schemas):
    """An enum slot carries its values directly, not a pointer to a definition."""
    status = synapse_schemas["Portal"]["properties"]["status"]
    assert status["enum"] == ["active", "in_development", "retired"]
    assert status["type"] == "string"


def test_nested_enums_are_inlined_too(synapse_schemas):
    """Flattening has to recurse — PERSON's enums sit inside an inlined object."""
    identifier = synapse_schemas["Person"]["properties"]["identifiers"]["items"]
    assert identifier["properties"]["identifier_type"]["enum"] == [
        "email", "username", "employee_id", "orcid_id",
    ]


def test_slot_description_survives_dereferencing(synapse_schemas):
    """The slot's own wording wins over the enum's generic description.

    A naive dereference replaces the whole ``$ref`` object and drops the sibling
    description LinkML emitted from the slot definition. That text is sourced
    from the Confluence entity spec, so losing it would be a real regression.
    """
    status = synapse_schemas["Portal"]["properties"]["status"]
    assert status["description"] == "Current lifecycle state of the portal."


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_property_titles_echo_the_property_name(class_name, synapse_schemas):
    for name, prop in synapse_schemas[class_name]["properties"].items():
        assert prop.get("title") == name


def test_enum_violations_are_still_rejected(synapse_schemas):
    """Flattening preserved the constraint, not just the shape."""
    validator = Draft7Validator(synapse_schemas["Portal"])
    bad = load_yaml(EXAMPLES / "portal.yaml") | {"status": "live"}
    assert any(e.validator == "enum" for e in validator.iter_errors(bad))


def test_id_pattern_is_still_enforced(synapse_schemas):
    validator = Draft7Validator(synapse_schemas["Program"])
    bad = load_yaml(EXAMPLES / "program.yaml") | {"id": "amp-ad"}
    assert any(e.validator == "pattern" for e in validator.iter_errors(bad))


def test_required_slots_are_still_required(synapse_schemas):
    validator = Draft7Validator(synapse_schemas["Portal"])
    bad = {k: v for k, v in load_yaml(EXAMPLES / "portal.yaml").items() if k != "url"}
    assert any(e.validator == "required" for e in validator.iter_errors(bad))


def test_nullable_unions_are_collapsed_by_default():
    """Optional slots carry a plain ``type``, matching the registered siblings.

    Synapse rejects an array-valued ``type`` outright -- confirmed by dry run,
    which fails with ``No enum constant ...Type.["string","null"]``. Collapsing
    is therefore required for registration, not a style choice, so this pins
    that it stays the default.
    """
    for class_name in ENTITY_CLASSES:
        schema = _build(class_name)
        assert not [v for k, v in _walk(schema) if k == "type" and isinstance(v, list)]


def test_keep_nullable_opts_out(tmp_path):
    """The opt-out restores LinkML's unions.

    The result is still valid draft-07 and still accepts the examples -- it is
    simply not registrable with Synapse, which is why it is not the default.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--keep-nullable", "--out-dir", str(tmp_path)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr

    unions = 0
    for class_name, filename in ENTITY_CLASSES.items():
        schema = json.loads((tmp_path / f"{class_name}.json").read_text())
        unions += len([v for k, v in _walk(schema)
                       if k == "type" and isinstance(v, list)])
        Draft7Validator.check_schema(schema)
        errors = [e.message for e in Draft7Validator(schema).iter_errors(
            load_yaml(EXAMPLES / filename))]
        assert not errors, "\n".join(errors)
    assert unions, "--keep-nullable should have left the unions in place"


def test_collapsing_does_not_loosen_type_checking():
    """Collapsing narrows what is accepted; it must not widen it.

    ``type: [string, null]`` accepts an explicit null, ``type: string`` does not.
    Synapse annotations model an unset value as an absent key, so nothing is lost
    -- but a null slipping through silently would be.
    """
    validator = Draft7Validator(_build("Portal"))
    instance = load_yaml(EXAMPLES / "portal.yaml") | {"launch_date": None}
    assert any(e.validator == "type" for e in validator.iter_errors(instance))


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_no_boolean_additional_properties(class_name):
    """Synapse's parser rejects a boolean ``additionalProperties`` outright.

    Draft-07 allows either a boolean or a schema, but Synapse only accepts a
    schema and fails the whole document with

        JSONObjectAdapterException: JSONObject["additionalProperties"]
        is not a JSONObject

    LinkML emits ``false`` on inlined classes and ``--not-closed`` puts ``true``
    on the root, so this has to hold at every depth, not just the top level.
    """
    offenders = [
        value for key, value in _walk(_build(class_name))
        if key == "additionalProperties" and isinstance(value, bool)
    ]
    assert not offenders
