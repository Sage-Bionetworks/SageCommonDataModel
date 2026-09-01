# SageCommonDataModel

LinkML source schemas for the **Sage Common Data Model (CDM)** — a unified structure for
organizing research programs, people, studies, and data standards across Sage Bionetworks.

The CDM enables cross-program queries, standards tracking, and operational reporting while
respecting each portal's flexibility to define programs in its own way. This repository holds
the machine-readable LinkML representation of the entities specified in Confluence; the
Confluence entity pages remain the human-readable specification of record.

## Governing references

| Reference | Purpose |
| --- | --- |
| [CDM Modeling Principles](https://sagebionetworks.jira.com/wiki/spaces/CDO/pages/4788846642/CDM+Modeling+Principles) | **The governing reference for this repository.** How CDM entities are designed, named, tiered, and evolved. Read this before adding or changing a class. |
| [Sage Common Data Model (CDM)](https://sagebionetworks.jira.com/wiki/spaces/CDO/pages/4237754409/Sage+Common+Data+Model+CDM) | Top-level CDM page — architecture, the three domains, entity implementation status, and roadmap. |
| [Entity: PORTAL](https://sagebionetworks.jira.com/wiki/spaces/CDO/pages/4788387865) | Reference implementation of a fully-tiered entity page. |
| [CoreModels](https://sage-bionetworks.github.io/core-models/) | Schema catalog and semantic registry across Sage. |

Anything in this repository that conflicts with the CDM Modeling Principles page should be
treated as a bug in this repository.

## Repository layout

```
src/         LinkML source files — base classes, mixins, and entity classes
examples/    Example instance files for each entity
tests/       Validation tests
scripts/     Build tooling (Synapse JSON Schema generation)
docs/        Generated documentation (populated later)
dist/        Generated artifacts — gitignored, regenerate with `make`
```

### Schema files

Import `src/sage_cdm.yaml` when you want the whole model; import an individual entity file
when you want just that class and its dependencies.

| File | Contents |
| --- | --- |
| `src/props.yaml` | Reusable slots (`id`, `name`, `description`, `status`, `url`, dates, provenance) and the shared `LifecycleStatusEnum` |
| `src/mixins.yaml` | `ProvenanceMixin` — where a record came from and who last touched it |
| `src/base_entity.yaml` | `BaseEntity`, the abstract supertype every entity extends |
| `src/organization.yaml` | `Organization` — a thin wrapper over [ROR](https://ror.org/) |
| `src/person.yaml` | `Person`, `PersonIdentifier` |
| `src/portal.yaml` | `Portal` and its own `PortalStatusEnum` |
| `src/program.yaml` | `Program` |
| `src/project.yaml` | `Project` |
| `src/study.yaml` | `Study` |
| `src/sage_cdm.yaml` | Umbrella schema; also defines the `Portfolio` container used for validating a document of many records |

Slots whose range is another CDM entity (`program`, `funding_source`, `primary_contact`, …)
are defined in the file that declares the class they point **at**, not in `props.yaml`.
Putting them in `props.yaml` would make it import every entity schema while every entity
schema imports it — a cycle LinkML cannot resolve. Each entity file lists the reference
slots it contributes in its header.

### Status

Phase 1 entities implemented: ORGANIZATION, PERSON, PORTAL, PROGRAM, PROJECT, STUDY.

Not yet implemented: the role-assignment relationship connecting PERSON to PROGRAM /
PROJECT / STUDY, and the many-to-many PROGRAM-to-PORTAL relationship — whether that is a
slot on PROGRAM or a separate PROGRAM_MAPPING table is an open modelling question awaiting
DMG sign-off, so neither PROGRAM nor PORTAL points at the other. Work is tracked on the
[SCDM board](https://sagebionetworks.jira.com/jira/software/c/projects/SCDM/boards/2391)
under [SCDM-1](https://sagebionetworks.jira.com/browse/SCDM-1).

## Working with the schema

```bash
pip install -e '.[test]'

pytest                                    # schema compiles, conventions hold, examples validate
linkml-lint src/sage_cdm.yaml             # style check
linkml-validate -s src/sage_cdm.yaml examples/portfolio.yaml
linkml-validate -s src/sage_cdm.yaml -C Program examples/program.yaml
gen-json-schema src/sage_cdm.yaml         # and gen-pydantic, gen-owl, gen-docs, …
```

The test suite covers three things: that every schema file compiles standalone (so a
missing `imports:` entry can't hide behind the umbrella schema), that the CDM Modeling
Principles conventions hold (snake_case attributes, every slot titled and described,
identifier prefixes enforced), and that the examples validate — including negative cases
asserting that malformed identifiers, free-text `status`, and unknown identifier source
systems are actually rejected.

## Instance records

Populated records — the actual instances of the entities described here — live in the
Synapse project [syn76967024](https://www.synapse.org/Synapse:syn76967024). This repository
holds the model, not the data.

The files under `examples/` are illustrative only: one hand-written record per entity, used
to exercise the schema in tests. They are not a source of instance data.

## Synapse JSON Schemas

The CDM entities can also be built as JSON Schemas suitable for registering with Synapse and
binding to Synapse entities.

### Registration organization

Synapse namespaces every schema under an organization, and the schema's `$id` embeds it:

| | |
| --- | --- |
| Organization | `org.synapse.sagecdm` (Synapse id `2181`, created 2026-09-01) |
| `$id` pattern | `https://repo-prod.prod.sagebase.org/repo/v1/schema/type/registered/org.synapse.sagecdm-<entity>` |
| Example | `…/registered/org.synapse.sagecdm-portal`, or `…-portal-1.0.0` when built with `--version` |

The name follows the convention used by other Sage repositories that build schemas this way.
Registering under a different organization is a `--org` flag away, but the organization has
to exist in Synapse first; the API rejects an unknown one with
`Organization with name: '…' not found`.

**Nothing is registered yet.** The build and its `--validate` step only ever dry-run, which
creates nothing. Actual registration is a deliberate, separate step — it is a durable,
versioned write to the organization above.

### Building

```bash
make synapse                                    # writes dist/synapse/<Entity>.json
python scripts/build_synapse_schemas.py --validate    # + dry-run against the Synapse API
python scripts/build_synapse_schemas.py --version 1.0.0
```

`--validate` needs credentials, from `SYNAPSE_AUTH_TOKEN` or `~/.synapseConfig`.

### Why the output is transformed

Synapse implements a subset of JSON Schema, so `gen-json-schema` output cannot be registered
as-is. Each of these was confirmed against the API, not assumed — a schema can be perfectly
valid draft-07 and still be rejected:

| Transform | Why |
| --- | --- |
| Dereference every `$ref`, drop `$defs` | Synapse does not resolve internal references. Enums land inline on the property that uses them. |
| `type: [X, "null"]` → `type: X` | Synapse rejects an array-valued type: `No enum constant …Type.["string","null"]`. LinkML marks every optional slot nullable. `--keep-nullable` opts out, but the result will not register. |
| Drop boolean `additionalProperties`, at any depth | Synapse accepts only a schema there, and fails the whole document otherwise: `JSONObject["additionalProperties"] is not a JSONObject`. |

Dereferencing keeps the referring object's own keywords, so the per-slot descriptions
sourced from the Confluence entity pages survive rather than being replaced by the enum's
generic wording.

One schema is generated per entity — anything descending from `BaseEntity`. That excludes
`BaseEntity` itself, `ProvenanceMixin`, the `Portfolio` document container, and
`PersonIdentifier`, which only ever appears nested inside PERSON.

## Conventions

Naming follows the CDM Modeling Principles page:

- **Attribute names** — lowercase, underscore-separated (`launch_date`)
- **Entity names in prose** — uppercase (`PORTAL`, `PROGRAM`)
- **Entity identifiers** — lowercase entity type, dot-separated (`portal.amp-als`)
- **Enum values** — lowercase, underscore-separated (`in_development`)
- **Dates** — ISO 8601 (`YYYY-MM-DD`)

## How to contribute

> **Placeholder.** Contribution guidelines and CI are being defined under
> [SCDM-3](https://sagebionetworks.jira.com/browse/SCDM-3) and will be documented here.

In the meantime: work on a branch, open a pull request, and get a review before merging to
`main`. New entities go to the Data Modeling Group (DMG) for review before being marked
Active.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
