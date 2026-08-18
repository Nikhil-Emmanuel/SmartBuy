# SmartBuy AI — Data Model (FROZEN v1.0)

Owner: Member 6 (Backend) + Member 2 (Data). Changes require Tech Lead sign-off.

Portability rule: **no dialect-specific SQL.** JSON columns use SQLAlchemy `JSON`, which maps to
`JSONB` on Postgres and `TEXT` on SQLite. All ids are `String(36)` UUID4 — no autoincrement, so
seed data and generated data never collide.

---

## 1. Normalized product schema

Every source (`MARKET_A`, `MARKET_B`, `MARKET_C`, public dataset) is transformed into exactly this.
Member 2's ETL owns the transform; nothing downstream ever sees a raw source row.

| Field | Type | Rules |
|---|---|---|
| `id` | str(36) PK | UUID4 |
| `source` | str(32) | `MARKET_A` \| `MARKET_B` \| `MARKET_C` |
| `external_product_id` | str(64) | id within the source |
| `name` | str(255) | title-cased, trimmed |
| `brand` | str(80) | canonicalized via `brand_aliases.json` |
| `category` | str(64) | must be in the **controlled category vocabulary** (§3) |
| `subcategory` | str(64) | must be in the vocabulary |
| `description` | text | ≤ 1200 chars |
| `price` | int | **paise-free rupees, integer.** Never float. |
| `original_price` | int | `>= price` |
| `discount_pct` | int | derived: `round(100*(orig-price)/orig)`, 0 if none |
| `rating` | float | 0.0–5.0, one decimal |
| `review_count` | int | ≥ 0 |
| `features` | JSON | `["waterproof", "insulated", ...]` from controlled feature vocabulary |
| `specs` | JSON | free-form `{"weight_g": 450, "temp_rating_c": -5}` |
| `availability` | str(16) | `in_stock` \| `low_stock` \| `out_of_stock` |
| `delivery_days` | int | 1–14 |
| `url` | str(512) | source product page |
| `image_url` | str(512) | |
| `tags` | JSON | `["winter", "beginner", "trekking"]` — drives goal suitability |
| `is_simulated` | bool | **true for all curated catalog rows.** Renders the demo-data badge. |
| `created_at` | datetime | |

**Cross-source linkage:** `product_group_key` (str(64), indexed) — a normalized
`brand|subcategory|key_spec` hash. Rows sharing this key are treated as the *same product listed on
different marketplaces*, which is what makes the price-comparison table meaningful rather than
decorative. Member 2 must ensure ~30% of curated SKUs appear on 2+ sources at different prices.

### Integer money, always
Prices are integer rupees everywhere — DB, API, optimizer, UI. Float money in a budget optimizer
produces `₹14999.999999` on stage. There is no acceptable reason to use a float here.

---

## 2. Tables

```
users(id, name, email, is_anonymous, created_at)

user_preferences(id, user_id→users, preferred_categories JSON, preferred_brands JSON,
                 min_price, max_price, price_bias, delivery_bias, updated_at)
    price_bias ∈ {value, balanced, premium}   delivery_bias ∈ {fast, standard}

sessions(id, user_id→users, state, slots JSON, question_count, intent,
         created_at, updated_at)
    state ∈ {INTAKE, SLOT_FILL, PLANNING, DISCOVERY, OPTIMIZING, PRESENTED, REFINING}

conversation_messages(id, session_id→sessions, role, content, meta JSON, created_at)
    role ∈ {user, assistant, system}

products(… §1 …)
    INDEX (category), (subcategory), (source), (price), (product_group_key)

product_interactions(id, user_id→users, product_id→products, interaction_type, created_at)
    interaction_type ∈ {viewed, clicked, liked, disliked, saved, not_interested, purchased}

shopping_plans(id, user_id→users, session_id→sessions, goal, goal_summary,
               budget_total, estimated_total, estimated_savings, currency,
               context JSON, status, created_at)
    status ∈ {draft, complete, budget_infeasible}

requirements(id, plan_id→shopping_plans, item_name, category, subcategory, priority,
             quantity, reason, est_price_min, est_price_max, search_terms JSON,
             is_owned, fulfillment_status, kb_item_key)
    priority ∈ {essential, recommended, optional}
    fulfillment_status ∈ {pending, fulfilled, unfulfilled, owned}

recommendations(id, plan_id, requirement_id→requirements, product_id→products,
                score, score_breakdown JSON, rank, badge, reasons JSON, created_at)
    badge ∈ {best_overall, best_budget, best_rated, best_premium, best_deal, null}

plan_bundles(id, plan_id→shopping_plans, preset, total_cost, total_savings,
             remaining_budget, utility_score, is_selected, created_at)
    preset ∈ {best_overall, best_budget, premium}

bundle_items(id, bundle_id→plan_bundles, requirement_id, product_id, quantity, line_total)

substitutions(id, plan_id, requirement_id, from_product_id, to_product_id,
              reason, price_delta, score_delta, created_at)

offers(id, product_id→products, offer_type, discount_pct, flat_discount,
       coupon_code, description, valid_from, valid_to)
    offer_type ∈ {discount, coupon, bank_offer, bundle}

feedback(id, user_id, session_id, product_id, plan_id, feedback_type, comment, created_at)
    feedback_type ∈ {relevant, not_relevant, saved, not_interested}

audit_logs(id, user_id, session_id, action, tool, input_summary, output_summary,
           model_version, latency_ms, status, created_at)
```

### Why the four tables not listed in the master prompt exist
`sessions` and `conversation_messages` — the agent is stateful across turns and the chat must
survive a page refresh during the demo. `plan_bundles` and `bundle_items` — master prompt §21
requires three switchable bundles per plan; a plan cannot hold three totals in one row.

---

## 3. Controlled vocabularies

Hard-coded in `backend/app/kb/vocabulary.py`. **Every catalog row and every KB item must use
these exact strings.** This is the contract between Member 2's data and Member 4's knowledge base —
if they drift, requirements silently match zero products, which is the single most likely way this
project fails on stage.

```
CATEGORIES = [footwear, clothing, outerwear, equipment, electronics, safety,
              camping, hydration, navigation, accessories, furniture, kitchen,
              bedding, storage, personal_care]

PRIORITIES  = [essential, recommended, optional]
SOURCES     = [MARKET_A, MARKET_B, MARKET_C]

FEATURES    = [waterproof, water_resistant, windproof, insulated, thermal, breathable,
               lightweight, quick_dry, anti_slip, adjustable, foldable, rechargeable,
               shock_absorbing, uv_protection, machine_washable, ...]
```

A CI check (`scripts/validate_vocab.py`) fails the build if any product or KB item uses a category,
priority, source, or feature outside these lists. Run it after every data regeneration.

---

## 4. Requirement Knowledge Base format

Location: `backend/app/kb/goals/*.yaml`. Owner: Member 4.

```yaml
key: winter_trek
extends: trek                      # inherits all parent items, may override by item key
display_name: Winter Trekking
domain: outdoor
context_defaults:
  region_type: mountain
  temp_min_c: -5

items:
  - key: thermal_base_layer
    item_name: Thermal Base Layer
    category: clothing
    subcategory: thermals
    priority: essential
    quantity_rule: "ceil(duration_days / 2)"      # restricted DSL, see below
    conditions:
      - "temp_min_c < 12"
    reason: "Traps body heat in sub-12°C conditions; the base of any cold-weather layering system."
    search_terms: [thermal base layer, winter thermals, merino base layer]
    required_features: [thermal]
    preferred_features: [quick_dry, lightweight]
    est_price_range: [800, 2500]

  - key: sleeping_bag
    priority: essential
    conditions:
      - "camping == true"
      - "temp_min_c < 5"
    ...
```

**Restricted condition DSL.** Conditions are parsed with `ast.literal_eval`-style comparison
matching — **never `eval()`**. Grammar: `<slot> <op> <literal>` where
`op ∈ {<, <=, >, >=, ==, !=, in, not in}`. Unknown slot → condition evaluates `False` (fail-safe:
the item is simply not required). Same grammar for `quantity_rule`, restricted to
`ceil/floor/min/max` over slot arithmetic.

### Goals to author (in priority order — the demo depends on the first one)
1. `winter_trek` / `trek` ← **the demo. Must be flawless.**
2. `camping`
3. `apartment_setup`
4. `college_hostel`
5. `laptop_purchase` (validates Mode A: specific product search)

---

## 5. Preference learning (deliberately simple, honestly described)

An exponentially-weighted counter over feedback and interactions — no model, no training:

```
on liked/saved     → brand +0.3, category +0.2, observed price band +0.15
on disliked        → brand -0.3, category -0.15
on not_interested  → subcategory -0.4
decay 0.95 per session, scores clamped to [-1, 1]
```

Feeds the `preference_match` component of the ranking score. **We describe this as "preference
tracking", not "learning".** We do not claim long-term learning we have not built — master prompt §26.

---

## 6. Data volumes

| Dataset | Rows | Purpose |
|---|---|---|
| Curated catalog | ~3,000 SKUs across 3 sources | demo + all product surfaces |
| — trekking/outdoor | ~900 | primary demo domain, must be deep |
| — apartment/home | ~700 | second scenario |
| — electronics | ~700 | Mode A demo |
| — misc/accessories | ~700 | breadth |
| Offers | ~800 | ~25% of SKUs carry an offer |
| Synthetic interactions | ~15,000 | cold-start CF + admin dashboard numbers |
| Public dataset | as available | CF training + evaluation metrics only |

**Rule: no requirement in the `winter_trek` KB may have fewer than 6 matching candidate products.**
`scripts/validate_coverage.py` asserts this and must pass before the demo. A requirement with two
candidates makes the comparison table look broken.
