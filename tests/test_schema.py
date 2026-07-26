"""The schema compiles, and it obeys the CDM Modeling Principles conventions.

The compilation half of this satisfies the SCDM-5 acceptance criterion. The convention
half is the part that keeps paying off: naming and documentation drift is exactly what
the Modeling Principles page exists to prevent, and a reviewer should not have to catch
it by eye.
"""

import re

import pytest
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition

from conftest import ENTITY_CLASSES, SRC

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
CAMEL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

#: Files SCDM-5 names explicitly, plus the entity and umbrella schemas.
EXPECTED_SOURCE_FILES = [
    "base_entity.yaml",
    "mixins.yaml",
    "props.yaml",
    "organization.yaml",
    "person.yaml",
    "program.yaml",
    "project.yaml",
    "study.yaml",
    "sage_cdm.yaml",
]

PROVENANCE_SLOTS = {
    "source",
    "source_url",
    "created_by",
    "updated_by",
    "date_created",
    "date_updated",
}


# --------------------------------------------------------------------------
# Compilation
# --------------------------------------------------------------------------
@pytest.mark.parametrize("filename", EXPECTED_SOURCE_FILES)
def test_source_file_exists(filename):
    assert (SRC / filename).is_file(), f"src/{filename} is missing"


@pytest.mark.parametrize("filename", EXPECTED_SOURCE_FILES)
def test_each_schema_compiles_standalone(filename):
    """Each file resolves on its own, not just via the umbrella schema.

    Guards the import graph: if someone adds a slot referencing a class the file does
    not import, the umbrella schema would still resolve it and hide the break.
    """
    from linkml_runtime import SchemaView

    view = SchemaView(str(SRC / filename))
    assert view.schema.name


def test_expected_classes_present(schema_view):
    assert set(ENTITY_CLASSES).issubset(set(schema_view.all_classes()))


def test_base_entity_is_abstract(schema_view):
    base = schema_view.get_class("BaseEntity")
    assert base.abstract, "BaseEntity must be abstract — it is never instantiated directly"


def test_provenance_mixin_is_a_mixin_with_the_specified_slots(schema_view):
    mixin = schema_view.get_class("ProvenanceMixin")
    assert mixin.mixin, "ProvenanceMixin must be declared as a mixin"
    assert set(mixin.slots) == PROVENANCE_SLOTS


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_entity_extends_base_entity(schema_view, class_name):
    assert schema_view.get_class(class_name).is_a == "BaseEntity"


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_entity_inherits_provenance(schema_view, class_name):
    """Provenance reaches every entity through BaseEntity, not by being repeated."""
    induced = set(schema_view.class_slots(class_name))
    assert PROVENANCE_SLOTS.issubset(induced)


@pytest.mark.parametrize("class_name", sorted(ENTITY_CLASSES))
def test_entity_id_is_an_identifier_with_a_prefix_pattern(schema_view, class_name):
    """Every entity narrows `id` to its own dot-prefixed pattern."""
    slot = schema_view.induced_slot("id", class_name)
    assert slot.identifier, f"{class_name}.id must be the identifier"
    assert slot.pattern, f"{class_name}.id must constrain its prefix via slot_usage"
    expected_prefix = {
        "Organization": "org",
        "Person": "person",
        "Program": "program",
        "Project": "project",
        "Study": "study",
    }[class_name]
    assert slot.pattern.startswith(
        f"^{expected_prefix}\\."
    ), f"{class_name}.id pattern should anchor on '{expected_prefix}.'"


# --------------------------------------------------------------------------
# CDM Modeling Principles conventions
# --------------------------------------------------------------------------
def _own_slots(schema_view):
    """Slots defined by this model, excluding anything pulled in from linkml:types."""
    return [
        (name, schema_view.get_slot(name))
        for name in schema_view.all_slots()
        if isinstance(schema_view.get_slot(name), SlotDefinition)
    ]


def test_slot_names_are_snake_case(schema_view):
    offenders = [name for name, _ in _own_slots(schema_view) if not SNAKE_CASE.match(name)]
    assert not offenders, f"attribute names must be lowercase snake_case: {offenders}"


def test_class_names_are_camel_case(schema_view):
    offenders = [
        name
        for name in schema_view.all_classes()
        if isinstance(schema_view.get_class(name), ClassDefinition)
        and not CAMEL_CASE.match(name)
    ]
    assert not offenders, f"class names must be CamelCase: {offenders}"


def test_every_slot_has_a_title_and_description(schema_view):
    """Modeling Principle 2: a field name alone is ambiguous."""
    missing_description = [n for n, s in _own_slots(schema_view) if not s.description]
    missing_title = [n for n, s in _own_slots(schema_view) if not s.title]
    assert not missing_description, f"slots missing a description: {missing_description}"
    assert not missing_title, f"slots missing a title: {missing_title}"


def test_every_class_has_a_description(schema_view):
    missing = [
        name
        for name in schema_view.all_classes()
        if not schema_view.get_class(name).description
    ]
    assert not missing, f"classes missing a description: {missing}"


def test_every_enum_value_is_snake_case_and_documented(schema_view):
    bad_case, undocumented = [], []
    for enum_name in schema_view.all_enums():
        enum = schema_view.get_enum(enum_name)
        for value_name, value in (enum.permissible_values or {}).items():
            if not SNAKE_CASE.match(value_name):
                bad_case.append(f"{enum_name}.{value_name}")
            if not value.description:
                undocumented.append(f"{enum_name}.{value_name}")
    assert not bad_case, f"enum values must be lowercase snake_case: {bad_case}"
    assert not undocumented, f"enum values missing a description: {undocumented}"


def test_lifecycle_status_values_match_the_spec(schema_view):
    """PROGRAM, PROJECT, and STUDY all specify this exact set."""
    enum = schema_view.get_enum("LifecycleStatusEnum")
    assert set(enum.permissible_values) == {"active", "planned", "completed", "on_hold"}


@pytest.mark.parametrize("class_name", ["Program", "Project", "Study"])
def test_lifecycle_entities_share_the_status_enum(schema_view, class_name):
    assert schema_view.induced_slot("status", class_name).range == "LifecycleStatusEnum"


def test_date_slots_use_the_date_type(schema_view):
    """Business dates are plain ISO 8601 dates; only provenance stamps carry a time."""
    for slot_name in ("start_date", "end_date"):
        assert schema_view.get_slot(slot_name).range == "date"
    for slot_name in ("date_created", "date_updated"):
        assert schema_view.get_slot(slot_name).range == "datetime"


def test_organization_is_a_thin_ror_wrapper(schema_view):
    """The spec is explicit that ORGANIZATION must not grow descriptive slots."""
    slots = set(schema_view.class_slots("Organization"))
    forbidden = {"description", "status", "address", "city", "parent_organization"}
    assert not (slots & forbidden), (
        "ORGANIZATION is deliberately thin — detailed metadata lives in ROR and resolves "
        f"via ror_id. Unexpected slots: {sorted(slots & forbidden)}"
    )


def test_person_has_no_canonical_identity_slots(schema_view):
    """PERSON captures identifiers; it does not resolve them.

    A single `orcid` or `email` slot would reintroduce the assumption the spec rejects:
    that one stable value per identifier type exists per person.
    """
    slots = set(schema_view.class_slots("Person"))
    forbidden = {"orcid", "email", "given_name", "family_name", "job_title"}
    assert not (slots & forbidden), (
        "PERSON follows 'capture, don't resolve' — identifiers are a repeatable structure. "
        f"Unexpected slots: {sorted(slots & forbidden)}"
    )
    assert "identifiers" in slots
    assert "display_name" in slots


def test_study_has_no_temporary_pi_slot(schema_view):
    """The STUDY spec recommends waiting for STUDY_TEAM rather than adding a stopgap."""
    assert "pi" not in set(schema_view.class_slots("Study"))
