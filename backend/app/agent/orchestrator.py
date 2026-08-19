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
import re
import time

from sqlalchemy import func, select
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
from app.models.product import Product
from app.models.session import ChatSession, ConversationMessage
from app.models.user import User
from app.schemas.agent import Assumption, ChatResponse, Slots
from app.services import plan_service
from app.services.product_search import get_search_service

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
    "thanks a lot", "thank you so much", "ok", "okay", "k", "kk", "cool",
    "nice", "great", "awesome", "sure", "yes", "yeah", "yep", "no", "nope",
    "bye", "goodbye", "see you", "test", "testing", "who are you",
    "what can you do", "what is this",
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


def _is_smalltalk(text: str) -> bool:
    """A greeting is not a shopping goal. Asking "what is your budget?" in
    reply to "hi" is the single most obviously robotic thing this agent could
    do.

    Membership in `_SMALLTALK` is the whole test. This used to also treat any
    message of two words or fewer as chit-chat, which is how "mobile" -- the
    most natural way there is to start a product search -- got answered with a
    greeting. Short is not the same as empty. Anything we do not recognise as
    conversational filler is a shopping query, and an honest "I could not find
    anything matching mobile" beats a greeting that ignores what was typed.
    """
    return text.strip().lower().strip("!.,?- ") in _SMALLTALK


# Words that constrain a search without naming anything new. "under 3,000"
# narrows whatever we were already looking at; "mobile" changes the subject.
# Telling the two apart is what stops a budget tweak from replacing the search
# query with the word "under".
_CONSTRAINT_WORDS = frozenset({
    "under", "below", "above", "over", "less", "than", "more", "max", "maximum",
    "min", "minimum", "budget", "rupees", "inr", "around", "about", "upto",
    "within", "cheap", "cheaper", "cheapest", "costly", "price", "priced",
    "cost", "only", "just", "and", "the", "for", "of", "with", "any", "some",
    "something", "anything", "one", "options", "option", "alternatives",
    "alternative", "please", "make", "keep", "that", "this", "them", "it",
    "instead", "show", "give", "want", "need", "looking", "find", "buy",
    "better", "best", "good", "other", "another", "same", "still", "also",
})


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", text.lower())
            if len(w) > 2 and w not in _CONSTRAINT_WORDS]


def _carries_new_subject(text: str) -> bool:
    """Does this message name a thing, or only constrain the last one?"""
    return bool(_content_words(text))


def _nothing_stocked(db: Session, query: str) -> bool:
    """True when this catalog demonstrably has nothing for the query.

    Two independent misses: the query cannot be placed on any shelf, and the
    text index matches no product at all. This is a claim about our catalog,
    not about the market -- we sell no phones, which is not the same as saying
    no phones exist (ADR-004: the catalog is curated, not the internet).
    """
    service = get_search_service()
    category, subcategory = service.infer_taxonomy(db, query)
    if category or subcategory:
        return False
    return not service.index.query(query, top_k=1)


def _stocked_categories(db: Session, limit: int = 6) -> list[str]:
    """The catalog's biggest shelves, read from the catalog rather than typed
    into a constant that goes stale the next time we reseed."""
    rows = db.execute(
        select(Product.category, func.count())
        .where(Product.category != "")
        .group_by(Product.category)
        .order_by(func.count().desc())
    ).all()
    return [category.replace("_", " ") for category, _ in rows[:limit]]


def _nothing_stocked_message(db: Session, query: str) -> tuple[str, list[str]]:
    subject = " ".join(_content_words(query)) or query.strip()
    shelves = _stocked_categories(db)
    text = f"I do not have any {subject} in this catalog."
    if shelves:
        listed = ", ".join(shelves[:-1]) + f" and {shelves[-1]}"
        text += f" It covers {listed}."
    text += (
        " Name something from those, or describe what you are getting ready "
        "for and I will work out the list."
    )
    return text, STARTER_CHIPS


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
    except Exception:
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
    except Exception as exc:
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
    except Exception as exc:
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
    smalltalk = _is_smalltalk(clean)

    # Has the user changed the subject? Deliberately decided from the message
    # rather than from `intent`, because the label is not trustworthy here: the
    # deterministic fallback tags anything it does not recognise while a plan
    # is open as GENERAL_RECOMMENDATION, so with Gemini down "mobile" and
    # "cheaper" arrive under the same name. What separates them is that one
    # names a subject the open plan does not cover and the other does not.
    new_subject = (
        intent != Intent.GOAL_BASED_SHOPPING
        and not smalltalk
        and not answering
        and not fallback.looks_goal_shaped(clean)
        and _carries_new_subject(clean)
        and _changes_subject(clean, plan, current)
    )

    # A new subject starts a clean slate. `Slots.merge` deliberately keeps the
    # first goal_text it ever saw, which is right while one goal is being
    # refined turn by turn and wrong the moment the user asks about something
    # else: typing "mobile" into a trekking conversation was answered with the
    # trekking plan, budget and all. The budget goes too -- Rs 20,000 was a
    # ceiling for shoes, not a standing preference.
    if new_subject:
        slots.goal_text = clean
        slots.activity = None
        # Deliberately the regex, not the LLM's extraction: asked to fill slots
        # for "mobile" with a trek in the history, Gemini helpfully carries the
        # old budget forward, and "mobile under Rs 15,000" is the same leak in
        # a smaller font. Only a figure typed in this message survives.
        slots.budget_total = fallback.extract_budget(clean)

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
    if (has_plan and intent in REFINEMENT_INTENTS
            and not new_subject and not _changed_activity(slots, plan)):
        return _refine(db, session, plan, slots, intent, degraded, user, already_asked)

    # ------------------------------------------------------- nothing stocked
    # Do not interrogate the user about something we cannot sell them. Asking
    # "what is your budget for the mobile phone?" and then answering "I could
    # not find anything matching mobile" spends their turn to reach a wall we
    # could already see.
    product_search = new_subject or (
        intent == Intent.SPECIFIC_PRODUCT_SEARCH
        and not fallback.looks_goal_shaped(clean)
    )
    if product_search and _nothing_stocked(db, slots.goal_text or clean):
        text, chips = _nothing_stocked_message(db, slots.goal_text or clean)
        session.state = AgentState.INTAKE
        _persist(db, session, slots)
        _save_message(db, session, MessageRole.ASSISTANT, text, {"chips": chips})
        return _response(session, slots, intent, text, chips,
                         next_action=NextAction.NONE, degraded=degraded,
                         asked=already_asked)

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
                # The slot we are asking about right now is still missing --
                # the sidebar highlights it while the user answers.
                asked=already_asked,
            )

    # ----------------------------------------------------------- build a plan
    session.state = AgentState.PLANNING
    _persist(db, session, slots)

    # An activity word inside a product name is not a goal. "Trekking shoes
    # under Rs 20,000" extracts activity="trek", and testing `not slots.activity`
    # sent it down the goal branch, which answered a request for one pair of
    # shoes with a fifteen-item trek kit. The purpose clause decides, not the
    # noun -- the same rule the deterministic intent detector already uses.
    if product_search:
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


def _plan_vocabulary(plan: ShoppingPlan) -> set[str]:
    """Every word the current plan is about: item names and their shelves."""
    words: set[str] = set()
    for requirement in plan.requirements:
        words.update(_content_words(requirement.item_name))
        for term in (requirement.category, requirement.subcategory,
                     *(requirement.search_terms or [])):
            if term:
                words.update(_content_words(str(term).replace("_", " ")))
    return words


def _changes_subject(text: str, plan: ShoppingPlan | None, current: Slots) -> bool:
    """Is this message about something other than what we are already showing?

    "a warmer jacket" against a trek plan refines it -- jacket is on the list.
    "mobile" against the same plan matches nothing in it, so it is a new
    subject rather than an adjustment to the old one. Comparing against the
    plan's own vocabulary keeps this honest: we do not need a list of every
    noun we sell, only the words this particular plan already covers.
    """
    if plan is None:
        return True
    vocabulary = _plan_vocabulary(plan) | set(_content_words(current.goal_text or ""))
    return not any(word in vocabulary for word in _content_words(text))


def _changed_activity(slots: Slots, plan: ShoppingPlan) -> bool:
    """True when the user has named a different activity than the plan's."""
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
