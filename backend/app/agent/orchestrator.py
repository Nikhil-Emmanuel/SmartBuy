"""The agent. A deterministic finite state machine, not an autonomous loop.

ADR-001: the agent does not choose its own tools. States and transitions are
fixed, the LLM is consulted at exactly three points, and every one of those
points has a deterministic fallback. The result is an agent that behaves the
same way in rehearsal and on stage.

    INTAKE -> SLOT_FILL -> PLANNING -> DISCOVERY -> OPTIMIZING -> PRESENTED
                  ^                                                  |
                  +---------------------- REFINING <-----------------+

Owner: Member 5 (Agentic AI).
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import fallback, slot_policy
from app.agent.llm import get_llm_provider
from app.agent.prompts import question_prompt, understand_prompt
from app.core.constants import (
    AgentState,
    BundlePreset,
    Intent,
    MessageRole,
    NextAction,
    PlanStatus,
)
from app.guardrails import validation
from app.guardrails.privacy import minimal_slots
from app.guardrails.recommendation_checks import check_question
from app.kb.loader import get_goal, list_goals
from app.logging import audit
from app.models.plan import ShoppingPlan
from app.models.session import ChatSession, ConversationMessage
from app.models.user import User
from app.schemas.agent import Assumption, ChatResponse, Slots
from app.services import plan_service

log = logging.getLogger("smartbuy.agent")

# Intents that operate on a plan the user already has.
REFINEMENT_INTENTS = frozenset({
    Intent.BUDGET_OPTIMIZATION,
    Intent.FIND_ALTERNATIVE,
    Intent.FIND_BEST_DEAL,
    Intent.PRODUCT_COMPARISON,
    Intent.GENERAL_RECOMMENDATION,
})


_SMALLTALK = frozenset({
    "hi", "hello", "hey", "yo", "hola", "namaste", "start", "help", "hi there",
    "good morning", "good afternoon", "good evening", "thanks", "thank you",
    "ok", "okay", "cool", "nice",
})

GREETING = (
    "Tell me what you are shopping for. You can describe a whole situation -- "
    "a trip, a new flat, a hobby you are starting -- and I will work out what "
    "you need, or just name a product if you already know."
)

STARTER_CHIPS = [
    "4-day trek in Manali",
    "Setting up my first flat",
    "Waterproof shoes under Rs 3,000",
]


def rs(amount: int | None) -> str:
    return f"Rs {int(amount):,}" if amount else "Rs 0"


def _is_smalltalk(text: str, slots: Slots) -> bool:
    """A greeting is not a shopping goal. Asking "what is your budget?" in
    reply to "hi" is the single most obviously robotic thing this agent could
    do."""
    stripped = text.strip().lower().strip("!.,?- ")
    if stripped in _SMALLTALK:
        return True
    return (
        len(stripped.split()) <= 2
        and not slots.activity
        and not slots.budget_total
    )


# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------
def create_session(db: Session, user: User | None = None) -> ChatSession:
    session = ChatSession(
        user_id=user.id if user else None,
        state=AgentState.INTAKE,
        slots={},
        assumptions=[],
    )
    db.add(session)
    db.flush()
    return session


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def latest_plan(db: Session, session_id: str) -> ShoppingPlan | None:
    return db.scalars(
        select(ShoppingPlan)
        .where(ShoppingPlan.session_id == session_id)
        .order_by(ShoppingPlan.created_at.desc())
    ).first()


def session_slots(session: ChatSession) -> Slots:
    try:
        return Slots(**(session.slots or {}))
    except Exception:  # noqa: BLE001 - a corrupt slot blob must not end the session
        log.exception("Could not load slots for session %s; starting clean", session.id)
        return Slots()


def asked_slots(db: Session, session: ChatSession) -> set[str]:
    """Every slot we have already put to the user in this session.

    The conversation itself is the record -- no extra column, and it survives
    a page refresh for free.
    """
    rows = db.scalars(
        select(ConversationMessage.meta)
        .where(ConversationMessage.session_id == session.id,
               ConversationMessage.role == MessageRole.ASSISTANT)
    ).all()
    return {meta["asked_slot"] for meta in rows
            if isinstance(meta, dict) and meta.get("asked_slot")}


def pending_slot(db: Session, session: ChatSession) -> str | None:
    """The slot the last assistant turn asked about, if any."""
    last = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session.id,
               ConversationMessage.role == MessageRole.ASSISTANT)
        .order_by(ConversationMessage.created_at.desc())
    ).first()
    if last is None or not isinstance(last.meta, dict):
        return None
    return last.meta.get("asked_slot")


def _save_message(db: Session, session: ChatSession, role: str, content: str,
                  meta: dict | None = None) -> ConversationMessage:
    message = ConversationMessage(
        session_id=session.id, role=role, content=content, meta=meta or {}
    )
    db.add(message)
    db.flush()
    return message


# --------------------------------------------------------------------------
# LLM call #1 -- understand
# --------------------------------------------------------------------------
def understand(db: Session, session: ChatSession, message: str, current: Slots,
               has_plan: bool) -> tuple[Intent, Slots, bool]:
    """Extract intent and slots. Returns (intent, slots, degraded).

    The deterministic extractor runs first and always. The LLM then refines
    it: regex is better at "Rs 15,000" and the model is better at "about
    fifteen thousand or so". When the model is unavailable we still have a
    complete answer, which is why the chaos test passes.
    """
    base_intent, base_slots = fallback.understand(message, current, has_plan)

    provider = get_llm_provider()
    if not provider.available:
        return base_intent, base_slots, True

    goal_keys = {g.key for g in list_goals()}
    system, user_prompt = understand_prompt(
        message=message,
        current_slots=minimal_slots(current.to_context()),
        has_plan=has_plan,
    )

    started = time.perf_counter()
    try:
        payload = provider.generate_json(system, user_prompt, max_output_tokens=700)
    except Exception as exc:  # noqa: BLE001 - any failure means fall back
        audit.record(
            db, action="llm_call", tool="understand", session_id=session.id,
            input_summary=message, output_summary=str(exc),
            model_version=provider.model, status=audit.STATUS_FALLBACK,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        log.info("understand() fell back to deterministic NLU: %s", exc)
        return base_intent, base_slots, True

    intent = validation.coerce_intent(payload.get("intent")) or base_intent
    llm_slots = validation.coerce_slots(payload.get("slots") or {}, goal_keys)
    llm_items = validation.coerce_existing_items(payload.get("existing_items"))

    merged = base_slots.model_copy(deep=True)
    for key, value in llm_slots.items():
        setattr(merged, key, value)
    merged.existing_items = list(dict.fromkeys([*base_slots.existing_items, *llm_items]))

    audit.record(
        db, action="llm_call", tool="understand", session_id=session.id,
        input_summary=message,
        output_summary=f"intent={intent} slots={sorted(llm_slots)}",
        model_version=provider.model, status=audit.STATUS_OK,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return intent, merged, False


# --------------------------------------------------------------------------
# LLM call #2 -- ask
# --------------------------------------------------------------------------
def ask(db: Session, session: ChatSession, slot: str, template: str,
        chips: list[str], slots: Slots) -> tuple[str, list[str], bool]:
    """Phrase one follow-up question. The slot choice is ours, not the model's."""
    provider = get_llm_provider()
    if not provider.available:
        return template, chips, True

    system, user_prompt = question_prompt(
        slot, template, chips, minimal_slots(slots.to_context())
    )

    started = time.perf_counter()
    try:
        payload = provider.generate_json(system, user_prompt, max_output_tokens=300)
    except Exception as exc:  # noqa: BLE001
        audit.record(
            db, action="llm_call", tool="ask", session_id=session.id,
            input_summary=slot, output_summary=str(exc),
            model_version=provider.model, status=audit.STATUS_FALLBACK,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return template, chips, True

    question, final_chips = check_question(payload, template, chips)
    audit.record(
        db, action="llm_call", tool="ask", session_id=session.id,
        input_summary=slot, output_summary=question,
        model_version=provider.model,
        status=audit.STATUS_OK if question != template else audit.STATUS_BLOCKED,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return question, final_chips, False


# --------------------------------------------------------------------------
# Presentation text -- deterministic, grounded by construction
# --------------------------------------------------------------------------
def _plan_message(plan: ShoppingPlan, creation: plan_service.PlanCreation) -> str:
    requirements = list(plan.requirements)
    owned = [r for r in requirements if r.is_owned]
    to_buy = [r for r in requirements if not r.is_owned]
    essentials = [r for r in to_buy if r.priority == "essential"]

    goal = get_goal(plan.goal_key)
    label = goal.display_name.lower() if goal else "your plan"

    lines = [
        f"Here is what you need for {label}: {len(to_buy)} items, "
        f"{len(essentials)} of them essential."
    ]

    if owned:
        names = ", ".join(r.item_name.lower() for r in owned[:4])
        lines.append(
            f"I have left out {len(owned)} item(s) you already have ({names})."
        )

    bundle = plan_service.selected_bundle(plan)
    if bundle is None:
        lines.append("I could not find products for these requirements yet.")
        return " ".join(lines)

    if plan.status == PlanStatus.BUDGET_INFEASIBLE:
        lines.append(
            f"Your budget of {rs(plan.budget_total)} does not stretch to every "
            f"essential. I have covered {len(bundle.items)} of them for "
            f"{rs(bundle.total_cost)} and listed what is missing."
        )
    else:
        lines.append(
            f"The recommended basket comes to {rs(bundle.total_cost)}, "
            f"saving {rs(bundle.total_savings)} against list prices"
        )
        if plan.budget_total:
            lines[-1] += f" and leaving {rs(bundle.remaining_budget)} of your " \
                         f"{rs(plan.budget_total)} budget."
        else:
            lines[-1] += "."

    if creation.unmatched_existing:
        items = ", ".join(creation.unmatched_existing[:3])
        lines.append(
            f"You mentioned {items} -- I could not match that to anything on the "
            f"list, so nothing was excluded for it."
        )

    return " ".join(lines)


def _search_message(plan: ShoppingPlan) -> str:
    requirement = plan.requirements[0] if plan.requirements else None
    if requirement is None:
        return "I could not work out what to search for. Could you rephrase that?"

    bundle = plan_service.selected_bundle(plan)
    if bundle is None or not bundle.items:
        return (
            f"I could not find anything matching {requirement.item_name.lower()}"
            + (f" under {rs(plan.budget_total)}" if plan.budget_total else "")
            + ". Try widening the budget or describing it differently."
        )

    ceiling = f" under {rs(plan.budget_total)}" if plan.budget_total else ""
    return (
        f"Here are the best matches for {requirement.item_name.lower()}{ceiling}, "
        f"compared across all three marketplaces."
    )


# --------------------------------------------------------------------------
# The turn
# --------------------------------------------------------------------------
def handle_message(db: Session, session: ChatSession, message: str,
                   user: User | None = None) -> ChatResponse:
    """One conversational turn, start to finish."""
    raw = message or ""
    clean = validation.sanitize_message(raw)
    flags = validation.detect_injection(raw)

    if flags:
        # We do not refuse to shop. We record it, and the prompt's data-block
        # framing means the text was never treated as an instruction anyway.
        log.warning("Prompt-injection patterns in session %s: %s", session.id, flags[:3])
        audit.record(db, action="guardrail", tool="injection_filter",
                     session_id=session.id, input_summary=raw,
                     output_summary=", ".join(flags[:3]), status=audit.STATUS_BLOCKED)

    current = session_slots(session)
    plan = latest_plan(db, session.id)
    has_plan = plan is not None
    answering = pending_slot(db, session)
    already_asked = asked_slots(db, session)

    _save_message(db, session, MessageRole.USER, clean, {"flagged": bool(flags)})

    intent, extracted, degraded = understand(db, session, clean, current, has_plan)

    # A short reply to our own question is an answer, not a new goal.
    # "Camping overnight" answering "camping or guesthouses?" must not silently
    # switch a winter trek plan into a camping plan.
    if answering and current.activity and len(clean.split()) < 8:
        extracted.activity = current.activity
        if intent != Intent.GOAL_BASED_SHOPPING:
            intent = Intent.GOAL_BASED_SHOPPING

    slots = current.merge(extracted)
    smalltalk = _is_smalltalk(clean, slots)
    if not slots.goal_text and not smalltalk:
        slots.goal_text = clean

    session.intent = str(intent)

    # ------------------------------------------------------------ small talk
    if smalltalk and not has_plan:
        session.state = AgentState.INTAKE
        _persist(db, session, slots)
        _save_message(db, session, MessageRole.ASSISTANT, GREETING,
                      {"chips": STARTER_CHIPS})
        return _response(session, slots, intent, GREETING, STARTER_CHIPS,
                         next_action=NextAction.NONE, degraded=degraded,
                         asked=already_asked)

    # ---------------------------------------------------------------- refine
    if has_plan and intent in REFINEMENT_INTENTS and not _is_new_goal(slots, plan):
        return _refine(db, session, plan, slots, intent, degraded, user, already_asked)

    # ------------------------------------------------------------- slot fill
    if not slot_policy.ready_to_plan(slots, intent, session.question_count,
                                     already_asked):
        pending = slot_policy.next_question(
            slots, intent, session.question_count, already_asked
        )
        if pending is not None:
            slot, template, chips = pending
            question, final_chips, ask_degraded = ask(
                db, session, slot, template, chips, slots
            )
            session.state = AgentState.SLOT_FILL
            session.question_count += 1
            _persist(db, session, slots)
            _save_message(db, session, MessageRole.ASSISTANT, question,
                          {"chips": final_chips, "asked_slot": slot})
            return _response(
                session, slots, intent, question, final_chips,
                next_action=NextAction.ANSWER_QUESTION,
                degraded=degraded or ask_degraded,
                asked=already_asked | {slot},
            )

    # ----------------------------------------------------------- build a plan
    session.state = AgentState.PLANNING
    _persist(db, session, slots)

    if intent == Intent.SPECIFIC_PRODUCT_SEARCH and not slots.activity:
        creation = plan_service.create_search_plan(
            db, query=slots.goal_text or clean, price_max=slots.budget_total,
            user=user, session_id=session.id,
        )
        text = _search_message(creation.plan)
        next_action = NextAction.VIEW_PLAN
    else:
        creation = plan_service.create_plan(
            db, slots=slots.to_context(), user=user, session_id=session.id,
        )
        if not creation.goal_resolved:
            # We could not resolve a goal, so treat it as a product search
            # rather than returning an empty plan.
            db.delete(creation.plan)
            db.flush()
            creation = plan_service.create_search_plan(
                db, query=slots.goal_text or clean, price_max=slots.budget_total,
                user=user, session_id=session.id,
            )
            text = _search_message(creation.plan)
            next_action = NextAction.VIEW_PLAN
        else:
            text = _plan_message(creation.plan, creation)
            next_action = NextAction.VIEW_REQUIREMENTS

    # Inferred context (season, region) becomes a visible, correctable
    # assumption rather than a hidden decision.
    assumptions = creation.assumptions
    session.assumptions = assumptions
    _apply_inferred(slots, creation.plan.context or {})

    session.state = AgentState.PRESENTED
    _persist(db, session, slots)
    _save_message(db, session, MessageRole.ASSISTANT, text,
                  {"plan_id": creation.plan.id, "degraded": degraded})

    audit.record(db, action="plan_generated", tool="plan_service",
                 session_id=session.id, user_id=user.id if user else None,
                 input_summary=slots.goal_text,
                 output_summary=f"plan={creation.plan.id} "
                                f"requirements={len(creation.plan.requirements)}",
                 status=audit.STATUS_OK)

    return _response(
        session, slots, intent, text, [],
        next_action=next_action, plan_id=creation.plan.id, degraded=degraded,
        assumptions=assumptions, asked=already_asked,
    )


def _is_new_goal(slots: Slots, plan: ShoppingPlan) -> bool:
    """True when the user has moved on to a different goal entirely."""
    return bool(slots.activity and plan.goal_key and slots.activity != plan.goal_key)


def _refine(db: Session, session: ChatSession, plan: ShoppingPlan, slots: Slots,
            intent: Intent, degraded: bool, user: User | None,
            asked: set[str] | None = None) -> ChatResponse:
    """Act on a plan that already exists."""
    session.state = AgentState.REFINING

    if intent == Intent.BUDGET_OPTIMIZATION:
        if slots.budget_total and slots.budget_total != plan.budget_total:
            plan_service.update_budget(db, plan, slots.budget_total, user=user)
            bundle = plan_service.selected_bundle(plan)
            text = (
                f"Rebuilt your plan for {rs(slots.budget_total)}. "
                f"The basket is now {rs(bundle.total_cost if bundle else 0)}"
                + (f", leaving {rs(bundle.remaining_budget)}." if bundle else ".")
            )
        elif any(b.preset == BundlePreset.BEST_BUDGET for b in plan.bundles):
            bundle = plan_service.select_bundle(db, plan, BundlePreset.BEST_BUDGET)
            text = (
                f"Switched you to the budget basket: {rs(bundle.total_cost)}, "
                f"saving {rs(bundle.total_savings)}. Every essential is still covered."
            )
        else:
            text = ("Tell me the figure you want to stay under and I will rebuild "
                    "the plan around it.")
        next_action = NextAction.VIEW_PLAN

    elif intent == Intent.FIND_BEST_DEAL:
        bundle = plan_service.selected_bundle(plan)
        text = (
            f"Your current basket already saves {rs(bundle.total_savings if bundle else 0)} "
            f"against list prices. Open the plan to see the discount on each item."
        )
        next_action = NextAction.VIEW_PLAN

    elif intent in (Intent.FIND_ALTERNATIVE, Intent.PRODUCT_COMPARISON):
        text = (
            "Open any item in your plan to see the alternatives side by side -- "
            "cheaper, better rated and faster delivery are all one tap away."
        )
        next_action = NextAction.VIEW_PLAN

    else:
        text = "Your plan is ready. Tell me what you would like to change."
        next_action = NextAction.VIEW_PLAN

    _persist(db, session, slots)
    _save_message(db, session, MessageRole.ASSISTANT, text, {"plan_id": plan.id})

    return _response(session, slots, intent, text, [], next_action=next_action,
                     plan_id=plan.id, degraded=degraded, asked=asked)


# --------------------------------------------------------------------------
# Slot corrections from the sidebar
# --------------------------------------------------------------------------
def apply_slot_update(db: Session, session: ChatSession, updates: dict,
                      user: User | None = None) -> ChatSession:
    """Manual slot edit. Marks any existing plan stale rather than silently
    rebuilding it -- the user decides when to regenerate."""
    goal_keys = {g.key for g in list_goals()}
    safe = validation.coerce_slots(updates, goal_keys)
    if "existing_items" in updates:
        safe["existing_items"] = validation.coerce_existing_items(updates["existing_items"])

    slots = session_slots(session)
    for key, value in safe.items():
        setattr(slots, key, value)

    session.slots = slots.model_dump()
    plan = latest_plan(db, session.id)
    if plan is not None and safe:
        plan.is_stale = True

    db.flush()
    audit.record(db, action="slot_update", session_id=session.id,
                 input_summary=", ".join(sorted(safe)), status=audit.STATUS_OK)
    return session


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------
def _persist(db: Session, session: ChatSession, slots: Slots) -> None:
    session.slots = slots.model_dump()
    db.flush()


def _apply_inferred(slots: Slots, context: dict) -> None:
    """Copy derived context (season, region_type, temp_min_c) back onto slots."""
    for key in ("season", "region_type", "temp_min_c", "duration_days", "camping"):
        value = context.get(key)
        if value is not None and getattr(slots, key, None) is None:
            setattr(slots, key, value)


def _response(session: ChatSession, slots: Slots, intent: Intent, text: str,
              chips: list[str], next_action: NextAction, plan_id: str | None = None,
              degraded: bool = False, assumptions: list[dict] | None = None,
              asked: set[str] | None = None) -> ChatResponse:
    return ChatResponse(
        session_id=session.id,
        state=session.state,
        intent=intent,
        assistant_message=text,
        chips=chips,
        slots=slots,
        collected=slot_policy.collected(slots),
        missing=slot_policy.missing(slots, intent, asked),
        assumptions=[Assumption(**a) for a in (assumptions or session.assumptions or [])],
        progress=slot_policy.progress(slots, intent, asked),
        plan_id=plan_id,
        next_action=next_action,
        degraded=degraded,
    )
