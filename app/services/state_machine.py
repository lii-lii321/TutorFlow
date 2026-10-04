from app.models import LeadEvent
from app.utils.clock import utcnow

STAGES = ["new", "contacted", "qualified", "trial", "won", "lost"]

STAGE_LABELS = {
    "new": "新线索",
    "contacted": "已联系",
    "qualified": "已确认需求",
    "trial": "已试听",
    "won": "已成交",
    "lost": "已流失",
}

TRANSITIONS = {
    "new": {"contacted", "qualified", "lost"},
    "contacted": {"qualified", "trial", "new", "lost"},
    "qualified": {"trial", "contacted", "lost"},
    "trial": {"won", "lost", "qualified"},
    "won": set(),
    "lost": {"contacted"},
}


class InvalidTransition(Exception):
    def __init__(self, from_stage: str, to_stage: str):
        self.from_stage = from_stage
        self.to_stage = to_stage
        allowed = sorted(TRANSITIONS.get(from_stage, set()))
        super().__init__(f"cannot transition {from_stage} -> {to_stage} (allowed: {allowed})")


def can_transition(from_stage: str, to_stage: str) -> bool:
    return to_stage in TRANSITIONS.get(from_stage, set())


def build_transition_event(lead, to_stage: str, reason: str = "") -> LeadEvent:
    if to_stage == lead.stage:
        raise InvalidTransition(lead.stage, to_stage)
    if not can_transition(lead.stage, to_stage):
        raise InvalidTransition(lead.stage, to_stage)
    from_stage = lead.stage
    lead.stage = to_stage
    lead.updated_at = utcnow()
    return LeadEvent(lead_id=lead.id, from_stage=from_stage, to_stage=to_stage, reason=reason)
