"""Unit tests for the four FunctionTools. Pure functions, no API key or network needed."""

import pytest

from agent.tools import (
    diagnose_electrical_issue,
    diagnose_issue,
    get_setup_flow,
    get_string_recommendations,
)


# --- get_setup_flow -------------------------------------------------------

@pytest.mark.parametrize("bridge", ["strat", "Tele", "hardtail", "non floyd trem"])
def test_setup_flow_path_a(bridge):
    flow = get_setup_flow(bridge)
    assert flow["path"] == "A"
    steps = flow["steps"]
    assert len(steps) == 7
    action = next(i for i, s in enumerate(steps) if "Action" in s)
    radius = next(i for i, s in enumerate(steps) if "Radius" in s)
    assert action < radius


@pytest.mark.parametrize("bridge", ["tune-o-matic", "Les Paul TOM", "gibson", "epiphone"])
def test_setup_flow_path_b(bridge):
    flow = get_setup_flow(bridge)
    assert flow["path"] == "B"
    steps = flow["steps"]
    action = next(i for i, s in enumerate(steps) if "Action" in s)
    radius = next(i for i, s in enumerate(steps) if "Radius" in s)
    assert radius < action


@pytest.mark.parametrize("bridge", ["floyd-rose", "bigsby", "acoustic"])
def test_setup_flow_special_cases(bridge):
    flow = get_setup_flow(bridge)
    assert flow["path"] == "special"
    assert "steps" not in flow
    assert flow["notes"]


def test_setup_flow_unknown_bridge():
    flow = get_setup_flow("mystery bridge")
    assert flow["path"] == "unknown"


def test_truss_rod_is_always_before_other_adjustments():
    for bridge in ("strat", "tom"):
        steps = get_setup_flow(bridge)["steps"]
        assert "Truss Rod" in steps[1]


# --- diagnose_issue -------------------------------------------------------

def test_diagnose_issue_known_symptom():
    result = diagnose_issue("buzzing")
    assert result["symptom"] == "buzzing"
    assert result["likely_causes"]
    assert result["diagnostic_questions"]
    assert "Truss Rod" in result["steps_to_revisit"]


def test_diagnose_issue_normalizes_input():
    assert diagnose_issue("Tuning Instability")["likely_causes"] != [
        "Symptom not recognized in standard diagnostic list."
    ]


def test_diagnose_issue_unknown_symptom_falls_back():
    result = diagnose_issue("smells like toast")
    assert result["likely_causes"] == ["Symptom not recognized in standard diagnostic list."]
    assert result["steps_to_revisit"] == ["Full setup review recommended"]


# --- diagnose_electrical_issue -------------------------------------------

def test_diagnose_electrical_known_symptom():
    result = diagnose_electrical_issue("hum")
    assert result["likely_causes"]
    assert result["recommended_fixes"]
    assert result["outside_setup_reference"] is True


def test_diagnose_electrical_unknown_symptom_falls_back():
    result = diagnose_electrical_issue("glows in the dark")
    assert result["outside_setup_reference"] is True
    assert result["recommended_fixes"]


# --- get_string_recommendations ------------------------------------------

def test_string_recommendations_standard_tuning():
    result = get_string_recommendations("standard-e")
    assert result["recommended_gauges"]["medium"] == "10-46"
    assert result["scale_modifier"] is None
    assert result["style_modifier"] is None


def test_string_recommendations_drop_c_is_heavier_than_standard():
    assert get_string_recommendations("drop-c")["recommended_gauges"]["medium"] == "11-54"


def test_string_recommendations_unknown_tuning_uses_defaults():
    result = get_string_recommendations("quarter-tone nonsense")
    assert result["tuning"].startswith("Custom/unrecognized tuning")
    assert result["recommended_gauges"]["medium"] == "11-49"


@pytest.mark.parametrize(
    "scale, expected",
    [("24.75", "Shorter scale"), ("25.5", "Standard scale"), ("27", "Extended/baritone")],
)
def test_string_recommendations_scale_modifier(scale, expected):
    result = get_string_recommendations("standard-e", scale_length=scale)
    assert expected in result["scale_modifier"]


def test_string_recommendations_bad_scale_is_reported_not_raised():
    result = get_string_recommendations("standard-e", scale_length="long")
    assert "wasn't parsed" in result["scale_modifier"]


@pytest.mark.parametrize(
    "style, expected",
    [("fingerstyle", "lighter"), ("aggressive", "heavier"), ("lead", "bend")],
)
def test_string_recommendations_style_modifier(style, expected):
    result = get_string_recommendations("standard-e", playing_style=style)
    assert expected in result["style_modifier"]
