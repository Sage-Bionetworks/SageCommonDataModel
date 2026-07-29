"""Shared fixtures for the Sage CDM schema tests."""

from functools import lru_cache
from pathlib import Path

import pytest
import yaml
from linkml_runtime import SchemaView

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
EXAMPLES = REPO_ROOT / "examples"

MAIN_SCHEMA = SRC / "sage_cdm.yaml"

#: Every Phase 1 entity class.
ENTITY_CLASSES = ("Organization", "Person", "Program", "Project", "Study")

#: Files that are not single-entity examples and so are validated separately.
NON_ENTITY_EXAMPLES = {"portfolio.yaml"}


def example_files(class_name):
    """Example files for a class, by convention: examples/<lowercase class name>*.yaml.

    Globbing rather than an explicit map means populate tickets can drop in new instance
    files (SCDM-35's `program_nf_*.yaml`, and the PORTAL and PERSON population epics after
    it) and have them validated without touching the test suite. `test_every_example_is
    _claimed_by_a_class` is what stops a typo'd filename from being silently skipped.
    """
    return sorted(EXAMPLES.glob(f"{class_name.lower()}*.yaml"))


#: A single canonical example per class, used as the base for negative-case mutation.
CANONICAL_EXAMPLE = {
    "Organization": "organization.yaml",
    "Person": "person.yaml",
    "Program": "program.yaml",
    "Project": "project.yaml",
    "Study": "study.yaml",
}

#: Every (class, example file) pair, for parametrized validation.
EXAMPLE_CASES = [
    (class_name, path)
    for class_name in ENTITY_CLASSES
    for path in example_files(class_name)
]


@lru_cache(maxsize=1)
def validation_schema():
    """A single self-contained schema with every import merged in.

    The validator resolves a schema passed by path against the *current working
    directory* rather than against the schema file, so `imports: [organization]` breaks
    whenever pytest is invoked from anywhere but src/. Merging up front sidesteps that
    and means the suite passes from any directory.
    """
    view = SchemaView(str(MAIN_SCHEMA))
    view.merge_imports()
    return view.schema


@pytest.fixture(scope="session")
def schema_view() -> SchemaView:
    """The whole model, resolved through the umbrella schema."""
    return SchemaView(str(MAIN_SCHEMA))


def load_yaml(path: Path):
    with path.open() as handle:
        return yaml.safe_load(handle)
