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

#: Every Phase 1 entity class, and the example file holding a single instance of it.
ENTITY_CLASSES = {
    "Organization": "organization.yaml",
    "Person": "person.yaml",
    "Portal": "portal.yaml",
    "Program": "program.yaml",
    "Project": "project.yaml",
    "Study": "study.yaml",
}


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
