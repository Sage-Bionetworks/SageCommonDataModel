"""Every example instance file validates against the schema."""

import pytest
from linkml.validator import validate

from conftest import ENTITY_CLASSES, EXAMPLES, load_yaml, validation_schema


def _assert_valid(instance, target_class=None):
    report = validate(instance, validation_schema(), target_class)
    messages = [f"{r.severity} {r.message}" for r in report.results]
    assert not messages, "\n".join(messages)


@pytest.mark.parametrize("class_name,filename", sorted(ENTITY_CLASSES.items()))
def test_entity_example_validates(class_name, filename):
    _assert_valid(load_yaml(EXAMPLES / filename), class_name)


def test_portfolio_example_validates():
    """The connected example validates against the tree_root container."""
    _assert_valid(load_yaml(EXAMPLES / "portfolio.yaml"), "Portfolio")


def test_every_entity_has_an_example():
    for filename in ENTITY_CLASSES.values():
        assert (EXAMPLES / filename).is_file(), f"examples/{filename} is missing"


#: Portal instance drafts beyond the canonical example. They are staged here ahead of the
#: SCDM-7..15 population tickets, so they need to keep validating as the schema moves.
EXTRA_PORTAL_EXAMPLES = sorted(p.name for p in EXAMPLES.glob("portal_*.yaml"))


@pytest.mark.parametrize("filename", EXTRA_PORTAL_EXAMPLES)
def test_additional_portal_example_validates(filename):
    _assert_valid(load_yaml(EXAMPLES / filename), "Portal")


# --------------------------------------------------------------------------
# Negative cases — the constraints actually reject bad data
# --------------------------------------------------------------------------
def _is_invalid(instance, target_class):
    report = validate(instance, validation_schema(), target_class)
    return bool(report.results)


def test_id_without_the_entity_prefix_is_rejected():
    bad = load_yaml(EXAMPLES / "program.yaml") | {"id": "amp-ad"}
    assert _is_invalid(bad, "Program"), "an id missing its 'program.' prefix should fail"


def test_id_with_capitals_is_rejected():
    bad = load_yaml(EXAMPLES / "program.yaml") | {"id": "program.AMP-AD"}
    assert _is_invalid(bad, "Program"), "identifiers are lowercase"


def test_free_text_status_is_rejected():
    bad = load_yaml(EXAMPLES / "program.yaml") | {"status": "live"}
    assert _is_invalid(bad, "Program"), "status is a closed enum, not free text"


def test_missing_required_program_reference_is_rejected():
    bad = {k: v for k, v in load_yaml(EXAMPLES / "study.yaml").items() if k != "program"}
    assert _is_invalid(bad, "Study"), "every study belongs to exactly one program"


def test_malformed_ror_id_is_rejected():
    bad = load_yaml(EXAMPLES / "organization.yaml") | {"ror_id": "03cmr0k43"}
    assert _is_invalid(bad, "Organization"), "ror_id must be the full ROR URL"


def test_full_country_name_is_rejected():
    bad = load_yaml(EXAMPLES / "organization.yaml") | {"country": "United States"}
    assert _is_invalid(bad, "Organization"), "country is an ISO 3166-1 alpha-2 code"


def test_portal_status_from_the_shared_lifecycle_enum_is_rejected():
    """`planned` is valid for a program but meaningless for a portal."""
    bad = load_yaml(EXAMPLES / "portal.yaml") | {"status": "planned"}
    assert _is_invalid(bad, "Portal"), "PORTAL takes active / in_development / retired only"


def test_portal_without_a_url_is_rejected():
    """url is Min 1 on PORTAL even though the shared slot is optional elsewhere."""
    bad = {k: v for k, v in load_yaml(EXAMPLES / "portal.yaml").items() if k != "url"}
    assert _is_invalid(bad, "Portal"), "every portal has a public address"


def test_unknown_identifier_source_system_is_rejected():
    """The closed vocabulary is the point — unknown sources surface rather than vanish."""
    bad = load_yaml(EXAMPLES / "person.yaml")
    bad["identifiers"] = [
        {"source_system": "smartsheet", "identifier_type": "username", "source_value": "x"}
    ]
    assert _is_invalid(bad, "Person")
