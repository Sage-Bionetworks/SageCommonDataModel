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
docs/        Generated documentation (populated later)
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

Phase 1 entities implemented: ORGANIZATION, PERSON, PROGRAM, PROJECT, STUDY.

Not yet implemented: PORTAL ([SCDM-2](https://sagebionetworks.jira.com/browse/SCDM-2)), and
the role-assignment relationship connecting PERSON to PROGRAM / PROJECT / STUDY. Work is
tracked on the [SCDM board](https://sagebionetworks.jira.com/jira/software/c/projects/SCDM/boards/2391)
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
