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

These directories are currently empty placeholders. Schema development is tracked on the
[SCDM board](https://sagebionetworks.jira.com/jira/software/c/projects/SCDM/boards/2391):
foundational base classes land in
[SCDM-5](https://sagebionetworks.jira.com/browse/SCDM-5), followed by entity classes
(PORTAL, PROGRAM, PERSON, ORGANIZATION, …) under
[SCDM-1](https://sagebionetworks.jira.com/browse/SCDM-1).

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
