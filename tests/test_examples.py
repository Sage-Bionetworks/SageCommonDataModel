"""Every example instance file validates against the schema."""

import pytest
from linkml.validator import validate

from conftest import (
    CANONICAL_EXAMPLE,
    ENTITY_CLASSES,
    EXAMPLE_CASES,
    EXAMPLES,
    NON_ENTITY_EXAMPLES,
    example_files,
    load_yaml,
    validation_schema,
)


def _assert_valid(instance, target_class=None):
    report = validate(instance, validation_schema(), target_class)
    messages = [f"{r.severity} {r.message}" for r in report.results]
    assert not messages, "\n".join(messages)


@pytest.mark.parametrize(
    "class_name,path", EXAMPLE_CASES, ids=[p.name for _, p in EXAMPLE_CASES]
)
def test_entity_example_validates(class_name, path):
    _assert_valid(load_yaml(path), class_name)


def test_portfolio_example_validates():
    """The connected example validates against the tree_root container."""
    _assert_valid(load_yaml(EXAMPLES / "portfolio.yaml"), "Portfolio")


@pytest.mark.parametrize("class_name", ENTITY_CLASSES)
def test_every_entity_has_at_least_one_example(class_name):
    assert example_files(class_name), f"no example file for {class_name}"


def test_every_example_is_claimed_by_a_class():
    """A misnamed example file would otherwise be silently skipped rather than failing."""
    claimed = {path.name for _, path in EXAMPLE_CASES} | NON_ENTITY_EXAMPLES
    on_disk = {path.name for path in EXAMPLES.glob("*.yaml")}
    orphans = on_disk - claimed
    assert not orphans, (
        "these example files match no entity class and are not validated: "
        f"{sorted(orphans)}. Name them <class><suffix>.yaml — e.g. program_nf_x.yaml."
    )


def test_program_examples_populate_every_summary_tier_attribute():
    """SCDM-35 requires all Summary-tier attributes populated on each PROGRAM record."""
    summary_tier = {"id", "name", "description", "status"}
    for path in example_files("Program"):
        missing = summary_tier - set(load_yaml(path))
        assert not missing, f"{path.name} is missing Summary-tier fields: {sorted(missing)}"


def test_nf_program_examples_declare_a_funder():
    """funding_source is the one Business-tier PROGRAM attribute, and it is available here."""
    for path in example_files("Program"):
        if not path.name.startswith("program_nf_"):
            continue
        record = load_yaml(path)
        assert record.get("funding_source"), f"{path.name} should record its funder"


# --------------------------------------------------------------------------
# Negative cases — the constraints actually reject bad data
# --------------------------------------------------------------------------
def _canonical(class_name):
    return load_yaml(EXAMPLES / CANONICAL_EXAMPLE[class_name])


def _is_invalid(instance, target_class):
    report = validate(instance, validation_schema(), target_class)
    return bool(report.results)


def test_id_without_the_entity_prefix_is_rejected():
    assert _is_invalid(_canonical("Program") | {"id": "amp-ad"}, "Program")


def test_id_with_capitals_is_rejected():
    assert _is_invalid(_canonical("Program") | {"id": "program.AMP-AD"}, "Program")


def test_free_text_status_is_rejected():
    assert _is_invalid(_canonical("Program") | {"status": "live"}, "Program")


def test_missing_required_program_reference_is_rejected():
    bad = {k: v for k, v in _canonical("Study").items() if k != "program"}
    assert _is_invalid(bad, "Study"), "every study belongs to exactly one program"


def test_malformed_ror_id_is_rejected():
    bad = _canonical("Organization") | {"ror_id": "03cmr0k43"}
    assert _is_invalid(bad, "Organization"), "ror_id must be the full ROR URL"


def test_full_country_name_is_rejected():
    bad = _canonical("Organization") | {"country": "United States"}
    assert _is_invalid(bad, "Organization"), "country is an ISO 3166-1 alpha-2 code"


def test_unknown_identifier_source_system_is_rejected():
    """The closed vocabulary is the point — unknown sources surface rather than vanish."""
    bad = _canonical("Person")
    bad["identifiers"] = [
        {"source_system": "smartsheet", "identifier_type": "username", "source_value": "x"}
    ]
    assert _is_invalid(bad, "Person")
