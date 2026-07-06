"""tests/workflow/test_constitution.py — the 8-Article SDD constitution."""

from __future__ import annotations

from ooagent.workflow.constitution import ARTICLES


def test_constitution_has_exactly_eight_articles() -> None:
    assert len(ARTICLES) == 8


def test_constitution_numerals_are_roman_one_through_eight_in_order() -> None:
    expected = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
    assert [a.numeral for a in ARTICLES] == expected


def test_constitution_keys_are_unique() -> None:
    keys = [a.key for a in ARTICLES]
    assert len(keys) == len(set(keys))


def test_constitution_titles_match_expected_names() -> None:
    expected_titles = [
        "Form",
        "Security",
        "Governance",
        "Lifecycle",
        "Architecture",
        "Testing",
        "Zero Defects",
        "Traceability",
    ]
    assert [a.title for a in ARTICLES] == expected_titles
