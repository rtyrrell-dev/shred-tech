"""Guards the setup reference against regressions in safety-critical details."""

from agent.knowledge import SETUP_REFERENCE


def test_reference_is_not_empty():
    assert len(SETUP_REFERENCE) > 1000


def test_reference_makes_no_third_party_attribution():
    assert "MusicNomad" not in SETUP_REFERENCE
    assert "KISS" not in SETUP_REFERENCE


def test_tom_saddle_slots_slope_toward_tailpiece():
    # Irreversible step: the slot must slope to the back so the string breaks at the
    # saddle's front edge.
    assert "toward the tailpiece" in SETUP_REFERENCE
    assert "tilt the file down toward the headstock" not in SETUP_REFERENCE.lower()


def test_key_specs_present():
    for spec in ('0.010"', '0.012"', "4/64", "3/64", "1/8 turn"):
        assert spec in SETUP_REFERENCE
