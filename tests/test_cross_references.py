"""Cross-entity references in the connected example resolve, and obey the spec rules.

LinkML validates that a reference is well-formed, not that its target exists, and it has
no declarative way to express "this project must belong to the same program as the study
referencing it". Both are real constraints from the entity specs, so they are checked here.
"""

import pytest

from conftest import EXAMPLES, load_yaml


@pytest.fixture(scope="module")
def portfolio():
    return load_yaml(EXAMPLES / "portfolio.yaml")


@pytest.fixture(scope="module")
def ids_by_collection(portfolio):
    return {
        collection: {record["id"] for record in records}
        for collection, records in portfolio.items()
    }


def _references(portfolio):
    """Yield (holder_id, slot_name, referenced_id, collection_it_must_live_in)."""
    single = {
        "persons": [("primary_affiliation", "organizations")],
        "projects": [("program", "programs")],
        "studies": [
            ("program", "programs"),
            ("project", "projects"),
            ("primary_contact", "persons"),
        ],
    }
    multi = {
        "programs": [("funding_source", "organizations")],
        "projects": [("funding_source", "organizations")],
        "studies": [("contributing_organizations", "organizations")],
    }
    for collection, specs in single.items():
        for record in portfolio.get(collection, []):
            for slot, target_collection in specs:
                if slot in record:
                    yield record["id"], slot, record[slot], target_collection
    for collection, specs in multi.items():
        for record in portfolio.get(collection, []):
            for slot, target_collection in specs:
                for target in record.get(slot, []):
                    yield record["id"], slot, target, target_collection


def test_all_references_resolve(portfolio, ids_by_collection):
    dangling = [
        f"{holder}.{slot} -> {target!r} not found in {collection}"
        for holder, slot, target, collection in _references(portfolio)
        if target not in ids_by_collection.get(collection, set())
    ]
    assert not dangling, "dangling references:\n" + "\n".join(dangling)


def test_the_example_actually_exercises_every_reference_slot(portfolio):
    """Guards against the example quietly shrinking until it proves nothing."""
    exercised = {slot for _, slot, _, _ in _references(portfolio)}
    assert exercised == {
        "primary_affiliation",
        "funding_source",
        "program",
        "project",
        "primary_contact",
        "contributing_organizations",
    }


def test_study_project_belongs_to_the_same_program(portfolio):
    """From the STUDY spec: a study's project must sit within that study's program.

    Cannot be expressed in LinkML declaratively, so it is asserted here.
    """
    program_of_project = {p["id"]: p["program"] for p in portfolio.get("projects", [])}
    violations = [
        f"study {s['id']} is in {s['program']} but its project "
        f"{s['project']} is in {program_of_project[s['project']]}"
        for s in portfolio.get("studies", [])
        if "project" in s and program_of_project.get(s["project"]) != s["program"]
    ]
    assert not violations, "\n".join(violations)


def test_a_study_may_skip_the_project_level(portfolio):
    """The project level is optional and must not be faked with a synthetic record."""
    assert any(
        "project" not in study for study in portfolio["studies"]
    ), "the example should include a study that hangs directly off a program"


def test_end_date_only_appears_on_completed_records(portfolio):
    """From the PROJECT and STUDY specs: end_date is populated only when completed."""
    offenders = [
        f"{collection} {record['id']} has end_date but status is {record.get('status')!r}"
        for collection in ("projects", "studies")
        for record in portfolio.get(collection, [])
        if "end_date" in record and record.get("status") != "completed"
    ]
    assert not offenders, "\n".join(offenders)
