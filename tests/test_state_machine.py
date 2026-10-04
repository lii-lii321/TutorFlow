from types import SimpleNamespace

import pytest

from app.services.state_machine import InvalidTransition, build_transition_event, can_transition


def lead_at(stage: str):
    return SimpleNamespace(id=1, stage=stage, updated_at=None)


def test_valid_transition_creates_event():
    lead = lead_at("new")
    event = build_transition_event(lead, "contacted", reason="首次联系")
    assert lead.stage == "contacted"
    assert event.from_stage == "new"
    assert event.to_stage == "contacted"
    assert event.reason == "首次联系"


def test_invalid_jump_rejected():
    with pytest.raises(InvalidTransition):
        build_transition_event(lead_at("new"), "won")


def test_won_is_terminal():
    with pytest.raises(InvalidTransition):
        build_transition_event(lead_at("won"), "contacted")


def test_lost_reengagement_allowed():
    lead = lead_at("lost")
    build_transition_event(lead, "contacted")
    assert lead.stage == "contacted"


def test_same_stage_rejected():
    with pytest.raises(InvalidTransition):
        build_transition_event(lead_at("trial"), "trial")


def test_can_transition_table():
    assert can_transition("new", "contacted")
    assert can_transition("qualified", "trial")
    assert can_transition("trial", "lost")
    assert not can_transition("new", "trial")
    assert not can_transition("won", "lost")
    assert not can_transition("contacted", "won")
