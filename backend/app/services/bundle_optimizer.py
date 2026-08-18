"""Bundle optimizer -- choose one product per requirement, maximizing utility
subject to a total budget.

This is a multiple-choice knapsack. An exact solver is overkill at our scale
and, more importantly, produces an answer nobody can explain on stage. The
four-stage heuristic below is explainable at every step, which matters more:

    1. FEASIBILITY    cheapest viable pick for every essential.
                      If that already exceeds budget, say so honestly.
    2. GREEDY UPGRADE repeatedly apply the swap with the best utility gain per
                      rupee, while the total stays within budget.
    3. ADD-ONS        insert recommended, then optional, by the same ratio.
    4. LOCAL SEARCH   randomized single swaps to escape local optima.

Every difference between "what we would pick with unlimited budget" and "what
we actually picked" is recorded as a Substitution with a reason -- that is
what powers the "we swapped A for B because..." narrative.

Owner: Member 4 (Requirements/Optimization).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from app.core.constants import Availability, BundlePreset, Priority
from app.services.ranking import RankingConfig, get_ranking_config

log = logging.getLogger("smartbuy.optimizer")

# How much a requirement's score contributes to bundle utility. An essential
# item at 0.6 must outrank an optional item at 0.95.
PRIORITY_WEIGHT: dict[str, float] = {
    Priority.ESSENTIAL: 1.0,
    Priority.RECOMMENDED: 0.55,
    Priority.OPTIONAL: 0.25,
}

LOCAL_SEARCH_ITERATIONS = 200


@dataclass
class Candidate:
    product: object          # app.models.Product
    score: float
    breakdown: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def price(self) -> int:
        return int(self.product.price)

    @property
    def in_stock(self) -> bool:
        return self.product.availability != Availability.OUT_OF_STOCK


@dataclass
class RequirementCandidates:
    requirement: object      # PlannedRequirement or models.Requirement
    candidates: list[Candidate]

    @property
    def key(self) -> str:
        return getattr(self.requirement, "id", None) or getattr(
            self.requirement, "kb_item_key", ""
        )

    @property
    def priority(self) -> str:
        return getattr(self.requirement, "priority", Priority.ESSENTIAL)

    @property
    def quantity(self) -> int:
        return max(1, int(getattr(self.requirement, "quantity", 1) or 1))

    @property
    def name(self) -> str:
        return getattr(self.requirement, "item_name", "")

    def purchasable(self) -> list[Candidate]:
        """Out-of-stock products stay in the candidate pool for explanation,
        but must never be selected into a bundle."""
        return [c for c in self.candidates if c.in_stock]


@dataclass
class BundleItemResult:
    requirement: object
    candidate: Candidate
    quantity: int

    @property
    def line_total(self) -> int:
        return self.candidate.price * self.quantity

    @property
    def savings(self) -> int:
        p = self.candidate.product
        return max(0, int(p.original_price) - int(p.price)) * self.quantity


@dataclass
class SubstitutionResult:
    requirement: object
    from_candidate: Candidate
    to_candidate: Candidate
    reason: str

    @property
    def price_delta(self) -> int:
        return self.to_candidate.price - self.from_candidate.price

    @property
    def score_delta(self) -> float:
        return round(self.to_candidate.score - self.from_candidate.score, 4)


@dataclass
class BundleResult:
    preset: str
    items: list[BundleItemResult] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    substitutions: list[SubstitutionResult] = field(default_factory=list)
    infeasible: bool = False
    shortfall: int = 0
    budget: int = 0

    @property
    def total_cost(self) -> int:
        return sum(i.line_total for i in self.items)

    @property
    def total_savings(self) -> int:
        return sum(i.savings for i in self.items)

    @property
    def over_budget(self) -> int:
        """Amount by which this bundle exceeds the user's stated budget.

        Only the Premium preset can be non-zero (it is a deliberate stretch
        option). The UI shows this instead of a negative remaining balance,
        so we never imply the user's limit was respected when it was not.
        """
        if not self.budget:
            return 0
        return max(0, self.total_cost - self.budget)

    @property
    def remaining_budget(self) -> int:
        return max(0, self.budget - self.total_cost) if self.budget else 0

    @property
    def utility_score(self) -> float:
        """Average quality of the ESSENTIAL picks.

        Deliberately not averaged over every item: a bundle that also affords
        optional extras would otherwise score *lower* than a sparse one, which
        made Premium look worse than Budget. Breadth is reported separately as
        requirement_coverage and item count.
        """
        core = [i for i in self.items
                if getattr(i.requirement, "priority", "") == Priority.ESSENTIAL]
        pool = core or self.items
        if not pool:
            return 0.0
        return round(sum(i.candidate.score for i in pool) / len(pool), 4)

    @property
    def total_utility(self) -> float:
        """Priority-weighted sum -- rewards breadth as well as quality."""
        return round(sum(
            i.candidate.score * PRIORITY_WEIGHT.get(
                getattr(i.requirement, "priority", Priority.ESSENTIAL), 0.5)
            for i in self.items
        ), 4)

    @property
    def avg_rating(self) -> float:
        """Mean rating of the essential picks.

        Preset-neutral, unlike utility_score: each bundle's score is computed
        with its own weight vector, so those numbers are not comparable across
        presets. This is what actually answers "is Premium better gear?".
        """
        core = [i for i in self.items
                if getattr(i.requirement, "priority", "") == Priority.ESSENTIAL]
        pool = core or self.items
        if not pool:
            return 0.0
        return round(sum(i.candidate.product.rating for i in pool) / len(pool), 3)

    @property
    def avg_item_price(self) -> int:
        core = [i for i in self.items
                if getattr(i.requirement, "priority", "") == Priority.ESSENTIAL]
        pool = core or self.items
        return int(sum(i.candidate.price for i in pool) / len(pool)) if pool else 0


def _utility(rc: RequirementCandidates, candidate: Candidate,
             extras_multiplier: float = 1.0) -> float:
    weight = PRIORITY_WEIGHT.get(rc.priority, 0.5)
    if rc.priority != Priority.ESSENTIAL:
        weight *= extras_multiplier
    return candidate.score * weight


def _cheapest(rc: RequirementCandidates) -> Candidate | None:
    pool = rc.purchasable()
    return min(pool, key=lambda c: c.price) if pool else None


def _best(rc: RequirementCandidates) -> Candidate | None:
    pool = rc.purchasable()
    return max(pool, key=lambda c: c.score) if pool else None


def _substitution_reason(frm: Candidate, to: Candidate, rc: RequirementCandidates) -> str:
    saved = frm.price - to.price
    fp, tp = frm.product, to.product
    bits: list[str] = []

    if saved > 0:
        bits.append(f"saves Rs {saved:,}")
    elif saved < 0:
        bits.append(f"costs Rs {abs(saved):,} more")

    if tp.rating >= fp.rating:
        bits.append(f"rated {tp.rating} vs {fp.rating}")
    if tp.delivery_days < fp.delivery_days:
        bits.append(f"arrives {fp.delivery_days - tp.delivery_days} day(s) sooner")

    shared = set(fp.features or []) & set(tp.features or [])
    if len(shared) >= 2:
        bits.append(f"keeps {len(shared)} of the same key features")

    detail = ", ".join(bits) if bits else "closest available alternative"
    return f"Swapped to {tp.name} for {rc.name}: {detail}."


def optimize_bundle(
    requirement_candidates: list[RequirementCandidates],
    budget: int | None,
    preset: str = BundlePreset.BEST_OVERALL,
    cfg: RankingConfig | None = None,
    seed: int = 42,
) -> BundleResult:
    """Select one product per requirement within budget."""
    cfg = cfg or get_ranking_config()
    rng = random.Random(seed)

    multiplier = cfg.budget_multipliers.get(preset, 1.0)
    reserve = float(cfg.optimizer_setting("budget_reserve_pct", preset, 0.0))
    cap = int(budget * multiplier * (1 - reserve)) if budget else 0
    result = BundleResult(preset=preset, budget=budget or 0)

    with_candidates = [rc for rc in requirement_candidates if rc.purchasable()]
    for rc in requirement_candidates:
        if not rc.purchasable():
            result.excluded.append({
                "requirement_id": rc.key,
                "item_name": rc.name,
                "reason": "no_candidates",
                "detail": "No in-stock product matched this requirement.",
            })

    essentials = [rc for rc in with_candidates if rc.priority == Priority.ESSENTIAL]
    extras = [rc for rc in with_candidates if rc.priority != Priority.ESSENTIAL]
    extras.sort(key=lambda rc: (rc.priority != Priority.RECOMMENDED, rc.name))

    # ---------------------------------------------------------------- stage 1
    selection: dict[str, tuple[RequirementCandidates, Candidate]] = {}
    for rc in essentials:
        cheapest = _cheapest(rc)
        if cheapest:
            selection[rc.key] = (rc, cheapest)

    floor_cost = sum(c.price * rc.quantity for rc, c in selection.values())

    if cap and floor_cost > cap:
        # Even the cheapest essentials do not fit. Return the subset that does,
        # ordered by how much utility each rupee buys, plus an honest shortfall.
        result.infeasible = True
        result.shortfall = floor_cost - cap
        affordable: dict[str, tuple[RequirementCandidates, Candidate]] = {}
        running = 0
        ranked = sorted(
            selection.values(),
            key=lambda pair: -(_utility(pair[0], pair[1]) / max(1, pair[1].price * pair[0].quantity)),
        )
        for rc, cand in ranked:
            line = cand.price * rc.quantity
            if running + line <= cap:
                affordable[rc.key] = (rc, cand)
                running += line
            else:
                result.excluded.append({
                    "requirement_id": rc.key,
                    "item_name": rc.name,
                    "reason": "over_budget",
                    "detail": f"Cheapest option is Rs {line:,}, which does not fit the remaining budget.",
                })
        selection = affordable
        log.info("Bundle %s infeasible: floor %s > cap %s", preset, floor_cost, cap)
    elif not cap:
        # No budget stated: take the best of each essential outright.
        for rc in essentials:
            best = _best(rc)
            if best:
                selection[rc.key] = (rc, best)

    def total() -> int:
        return sum(c.price * rc.quantity for rc, c in selection.values())

    # ---------------------------------------------------------------- stage 2
    #
    # `ratio` maximizes utility per rupee -- the right objective for a value
    # bundle. `absolute` takes the biggest affordable quality jump, which is
    # what Premium needs: on a per-rupee basis a Rs 250 accessory always beats
    # a Rs 7,400 jacket upgrade, so a pure ratio strategy makes "Premium" mean
    # "more items" rather than "better gear".
    strategy = cfg.optimizer_setting("upgrade_strategy", preset, "ratio")
    extras_multiplier = float(cfg.optimizer_setting("extras_weight_multiplier", preset, 1.0))
    # Diminishing-returns floor, expressed as utility per Rs 1,000. Without it
    # the optimizer drains the budget to the last rupee chasing +0.005.
    min_gain = float(cfg.optimizer_setting("min_upgrade_utility_per_1000", preset, 0.0))
    min_addon_gain = float(cfg.optimizer_setting("min_addon_utility_per_1000", preset, 0.0))

    if cap and not result.infeasible:
        improved = True
        guard = 0
        while improved and guard < 500:
            improved = False
            guard += 1
            spent = total()
            best_move = None
            best_metric = 0.0

            for rc in essentials:
                if rc.key not in selection:
                    continue
                current = selection[rc.key][1]
                for cand in rc.purchasable():
                    if cand is current:
                        continue
                    d_util = _utility(rc, cand) - _utility(rc, current)
                    if d_util <= 0:
                        continue
                    d_cost = (cand.price - current.price) * rc.quantity

                    if d_cost <= 0:
                        # Strictly better and no more expensive: always take it.
                        selection[rc.key] = (rc, cand)
                        improved = True
                        break
                    if spent + d_cost > cap:
                        continue
                    if (d_util / d_cost) * 1000 < min_gain:
                        continue  # not worth the money

                    metric = d_util if strategy == "absolute" else d_util / d_cost
                    if metric > best_metric:
                        best_metric, best_move = metric, (rc, cand)
                if improved:
                    break

            if not improved and best_move:
                rc, cand = best_move
                selection[rc.key] = (rc, cand)
                improved = True

    # ---------------------------------------------------------------- stage 3
    for rc in extras:
        spent = total()
        headroom = (cap - spent) if cap else None
        pool = rc.purchasable()
        if headroom is not None:
            pool = [c for c in pool if c.price * rc.quantity <= headroom]
        if not pool:
            result.excluded.append({
                "requirement_id": rc.key,
                "item_name": rc.name,
                "reason": "budget_prioritized",
                "detail": f"{rc.priority.title()} item left out so the budget covers essentials.",
            })
            continue
        pick = max(pool, key=lambda c: _utility(rc, c, extras_multiplier)
                   / max(1, c.price * rc.quantity))
        gain = _utility(rc, pick, extras_multiplier) / max(1, pick.price * rc.quantity) * 1000
        if gain < min_addon_gain:
            result.excluded.append({
                "requirement_id": rc.key,
                "item_name": rc.name,
                "reason": "low_value",
                "detail": f"{rc.priority.title()} item skipped: not enough value for the cost.",
            })
            continue
        selection[rc.key] = (rc, pick)

    # ---------------------------------------------------------------- stage 4
    if cap and len(selection) > 1:
        all_selected = list(selection)
        for _ in range(LOCAL_SEARCH_ITERATIONS):
            key = rng.choice(all_selected)
            rc, current = selection[key]
            pool = rc.purchasable()
            if len(pool) < 2:
                continue
            cand = rng.choice(pool)
            if cand is current:
                continue
            d_cost = (cand.price - current.price) * rc.quantity
            if total() + d_cost > cap:
                continue
            if _utility(rc, cand, extras_multiplier) > _utility(rc, current, extras_multiplier):
                selection[key] = (rc, cand)

    # ---------------------------------------------------------------- output
    for rc, cand in selection.values():
        result.items.append(BundleItemResult(rc.requirement, cand, rc.quantity))

    result.items.sort(key=lambda i: (
        {"essential": 0, "recommended": 1, "optional": 2}.get(
            getattr(i.requirement, "priority", "essential"), 3),
        getattr(i.requirement, "item_name", ""),
    ))

    # Substitutions: what we would have picked with unlimited budget, versus
    # what the budget actually allowed.
    for rc in with_candidates:
        if rc.key not in selection:
            continue
        chosen = selection[rc.key][1]
        ideal = _best(rc)
        if ideal and ideal is not chosen and ideal.score - chosen.score > 0.01:
            result.substitutions.append(
                SubstitutionResult(rc.requirement, ideal, chosen,
                                   _substitution_reason(ideal, chosen, rc))
            )

    return result


def requirement_coverage(result: BundleResult, all_requirements: list) -> float:
    """Fraction of essential requirements the bundle actually fulfils."""
    essentials = [r for r in all_requirements
                  if getattr(r, "priority", "") == Priority.ESSENTIAL
                  and not getattr(r, "is_owned", False)]
    if not essentials:
        return 1.0
    covered = {id(i.requirement) for i in result.items}
    return round(sum(1 for r in essentials if id(r) in covered) / len(essentials), 4)


def optimize_presets(
    build_candidates,
    budget: int | None,
    presets: list[str] | None = None,
    seed: int = 42,
) -> list[BundleResult]:
    """Run the optimizer once per preset.

    `build_candidates(preset)` must return the requirement/candidate list
    scored with that preset's weights -- Budget and Premium are different
    answers precisely because they are scored differently, not just capped
    differently.
    """
    presets = presets or [
        BundlePreset.BEST_OVERALL, BundlePreset.BEST_BUDGET, BundlePreset.PREMIUM
    ]
    return [
        optimize_bundle(build_candidates(preset), budget, preset, seed=seed)
        for preset in presets
    ]
