"""Agent-facing schemas: the slot profile and the chat contract.

Mirrors docs/API_CONTRACT.md section 1.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import AgentState, Intent, NextAction


class SlotPreferences(BaseModel):
    brands: list[str] = Field(default_factory=list)
    price_bias: str = "balanced"      # value | balanced | premium
    delivery_bias: str = "standard"   # fast | standard


class Slots(BaseModel):
    """The structured requirement profile the agent accumulates.

    Every field is optional: the whole point is that we work with whatever the
    user gave us and infer or ask for the rest.
    """

    model_config = ConfigDict(extra="ignore")

    goal_text: str = ""
    activity: str | None = None
    location: str | None = None
    region_type: str | None = None
    season: str | None = None
    start_date: str | None = None
    duration_days: int | None = None
    people_count: int | None = None
    experience_level: str | None = None
    budget_total: int | None = None
    currency: str = "INR"
    camping: bool | None = None
    temp_min_c: int | None = None
    existing_items: list[str] = Field(default_factory=list)
    preferences: SlotPreferences = Field(default_factory=SlotPreferences)
    constraints: dict = Field(default_factory=dict)

    @field_validator("budget_total", mode="before")
    @classmethod
    def _clean_budget(cls, v):
        """Budgets arrive as '15000', '15,000', 'Rs 15000' or 15000.0."""
        if v is None or isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            digits = "".join(ch for ch in v if ch.isdigit())
            return int(digits) if digits else None
        return None

    @field_validator("duration_days", "people_count", mode="before")
    @classmethod
    def _clean_int(cls, v):
        if v is None or isinstance(v, int):
            return v
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            return None

    @field_validator("existing_items", mode="before")
    @classmethod
    def _clean_existing(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x).strip() for x in v if str(x).strip()]

    def merge(self, other: Slots) -> Slots:
        """Later turns win, but never overwrite a known value with None."""
        merged = self.model_copy(deep=True)
        for name in self.model_fields:
            new = getattr(other, name, None)
            if name == "existing_items":
                combined = list(dict.fromkeys([*merged.existing_items, *(new or [])]))
                merged.existing_items = combined
            elif name == "preferences":
                if new and (new.brands or new.price_bias != "balanced"
                            or new.delivery_bias != "standard"):
                    merged.preferences = new
            elif name == "goal_text":
                if new and not merged.goal_text:
                    merged.goal_text = new
            elif new is not None and new != "":
                setattr(merged, name, new)
        return merged

    def to_context(self) -> dict:
        data = self.model_dump()
        data["preferences"] = self.preferences.model_dump()
        return data


class Assumption(BaseModel):
    slot: str
    value: object = None
    basis: str = ""


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    state: AgentState
    intent: Intent | None = None
    assistant_message: str
    chips: list[str] = Field(default_factory=list)
    slots: Slots
    collected: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    progress: float = 0.0
    plan_id: str | None = None
    next_action: NextAction = NextAction.NONE
    # True when the LLM was unavailable and deterministic handling took over.
    # The journey still completes; only the prose is templated.
    degraded: bool = False


class MessageOut(BaseModel):
    role: str
    content: str
    meta: dict = Field(default_factory=dict)
    created_at: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    state: AgentState
    intent: Intent | None = None
    slots: Slots
    assumptions: list[Assumption] = Field(default_factory=list)
    messages: list[MessageOut] = Field(default_factory=list)
    plan_id: str | None = None


class SlotUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
