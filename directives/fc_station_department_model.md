# FC / Station / Department model — map & target

**Status:** MAP & DOCUMENT only. No code changes have been made from this doc.
It records the current ("as-is") model, the inconsistencies around **FC**, and
the owner's intended ("to-be") model, plus a change-list for a *future*
structural cleanup. Written 2026-06-26 (v2.21.82).

---

## 1. The intended 3-tier catalog (this part is clean)

| Tier | Table | Meaning | Examples |
|------|-------|---------|----------|
| **Line** | `manufacturing_line` (`line_id`) | A production line | P01, P02, P37 (main); PUV, PVS, PSP (aux); **FC** (prep) |
| **Department** | `departments` (`code`) | A *stage / type* of work | fc, laminating, cold_press, hot_press, bleach, repair, sanding, grading, packing, fg_receiving, fg_warehouse |
| **Station** | `stations` (`line_code` × `department_code`) | A department *on a specific line* | "P01 · Laminating", "P02 · Cold Press" |
| **Flow** | `line_flow` (`line_code`, `seq`, `department_code`) | Ordered stages per line | P01: fc → laminating → … → packing → fg_warehouse |

So the *clean* rule is: **department = the kind of work; station = that work on one line.**
`departments.is_centralised=1` (packing, fg_receiving, fg_warehouse) are line-less —
for those, a "station" is just the department (no line).

The naming wobble (secondary): the DB stores a batch's position as
`batches.current_department` (a *department*), but the UI calls it a **Station**,
and the per-line tables are named `station_stock` / `station_log` / `station_*`.
Same concept, two names. (Not the focus of this pass.)

---

## 2. The FC overloading — every role "FC" plays today

"FC" is at least **seven** distinct things, which is the core confusion. (Per §3,
the root error is #1 — FC is modeled as a production *department/stage*, when it's
actually the **Feed Center**, a material‑prep/QC layer between WH and the lines.)

1. **A department** — `departments.code='fc'`, listed as **seq 0 in EVERY main line's
   `line_flow`** (P01/P02/P37 all start `fc → laminating → …`). This makes FC look
   like a per-line first stage.
2. **A line** — `manufacturing_line.line_id='FC'` (type `prep`, "FC / Cutting"),
   added so FC is one centralised operation.
3. **The only active FC station is the central one** — `stations` has P01·fc, P02·fc,
   P37·fc but all are **`is_active=0`** (disabled); only `FC·fc` is active. So FC
   already behaves centralised, contradicting the per-line `line_flow` entries.
4. **FC Hub** — a dedicated page + ~15 `/api/fc/*` endpoints (`/fc/batches`,
   `/fc/stock`, `/fc/transfer-requests`, `/fc/movements`, `/fc/material-check`,
   `/fc/material-requirements`, `/fc/regrade`, `/fc/return-material`,
   `/fc/laminating-material-request`, …), separate from the Station Leader Hub.
5. **A stock counter** — `materials.fc_stock` (per-material FC-station stock,
   distinct from `current_stock` = total and `wlwh_stock`); ~143 references.
6. **A material-staging concept** — `fc_transfer_requests` (move raw stock to FC) +
   `production_orders.fc_confirmed` + `confirmed_face_veneer_id`/`confirmed_back_veneer_id`
   (FC confirms the veneer grade-mix before a batch can run).
7. **Conflated with Glue Mixing** — `core.js DEPT_LABEL` labels `fc` as
   **"FC / Glue Mixing"**, while `departments` and `SLH_DEPT_LABEL` label it
   **"FC / Cutting"**. Glue mixing is "virtual" (no batch ever sits at
   `current_department='glue_mix'`; mixers prep glue *for* batches in laminating).

### Current batch flow (as-is)
A production order on line P01 creates a batch at `current_department='fc'`.
It is cut at the (single, central) FC station, then `batch_movements` records
**fc → laminating**, and it runs the rest of P01's flow. Observed on live data:
18 releases `'' → fc`, then `fc → laminating` (12) / `fc → cold_press` (1).
Net effect: FC is *modeled* as a per-line stage (seq 0 of each line) but *operated*
as one central station.

---

## 3. Target model (owner's intent — CORRECTED)

> **FC = "Feed Center."** It is **not** a production stage/department and **not**
> "cutting" or "glue mixing." FC is a **material-prep / QC / staging layer that
> sits between the Warehouse and the production lines** — the intermediary that
> feeds approved materials into production.

**What the Feed Center actually does (owner's description):**
- Screens **all incoming raw materials** to confirm they're usable, so
  raw-material **NCG doesn't interrupt production capacity**.
- **Grades veneers** and has **permission to regrade** stock (`/api/fc/regrade`,
  veneer_regrade_log).
- **Keeps / stages components** — e.g. VCMX panels land in FC stock as a kept
  component; graded veneers are held ready for production.
- **Feeds** the prepped, approved materials to the production lines (a line's
  first *production* step, laminating, consumes FC-prepped material).

So `fc_stock` is genuinely special (it's the pool of QC'd/graded/regraded material
+ kept components that FC controls), and `fc_confirmed` / `confirmed_*_veneer_id`
is FC signing off the graded veneer for an order before it runs.

**Therefore the model should be:**
```
   Warehouse  ──►  FC (Feed Center: screen / grade / regrade / stage)  ──►  Production lines
                    └ holds fc_stock, components (VCMX), graded veneers      (enter at laminating)
```
- **FC is its own node** (the Feed Center, with the FC Hub as its workspace) — NOT
  one of the production departments and NOT a per-line stage.
- **Each main line's flow starts at `laminating`** (P01: laminating → cold_press →
  hot_press → bleach → repair → sanding → grading → packing → fg_warehouse). The
  `fc` seq-0 entries should come out of `line_flow`.
- FC is **not** a station inside the Station Leader Hub — it keeps its **own FC Hub**.
- Correct label everywhere: **"Feed Center" (FC)** — drop "FC / Cutting" and
  "FC / Glue Mixing".

### Confirmed decisions (from owner Q&A, 2026-06-26)
- **Every batch's material passes through FC first**, then laminating (FC is a
  mandatory feed step, not optional). VCMX is the known exception (its panels are
  *produced into* FC stock, then fed back out).
- **FC Hub stays a separate page**; FC is **not** added to the Station Leader Hub.
- **`fc_stock` stays its own special counter** (regrade permission + component
  keeping) — not folded into the generic station_stock model.

---

## 4. Change-list for a FUTURE structural cleanup (NOT done yet)

When/if the owner approves the structural pass, these are the touch-points:

1. **`line_flow`** — remove the `fc` seq-0 row from P01/P02/P37 (keep the `FC` line's
   own `fc`). Re-sequence each line so `laminating` is seq 0. *(DB migration — idempotent,
   self-healing per the dangling-FK pattern; test on a copy. The owner's dev server runs
   `--reload` on the live `erp.db`, so saving applies it live — keep it guarded.)*
2. **Batch release / first-stage logic** — decide what `current_department` a new batch
   starts at. Either keep a line-agnostic "central FC" holding state and move to
   `laminating`, or release batches straight to `laminating` and treat FC cutting as a
   pre-step tracked on the FC line. Audit `create_*` batch-release code + the FC Hub
   "release to laminating" path (`/api/fc/laminating-material-request`).
3. **Frontend flow constants** — `LINE_FLOW` (portal_planning.js) and the dept lists
   (`DEPTS`) carry the per-line fc; strip it so the boards/flows match.
4. **Label fix (cheap, can be done independently)** — settle `fc` = **"Feed Center"**
   (NOT "FC / Cutting" and NOT "FC / Glue Mixing"). Fix `core.js DEPT_LABEL`,
   `departments.label`, and `SLH_DEPT_LABEL` so all three agree on "Feed Center".
5. **Glue Mixing relationship** — decide if glue_mix is a sub-function of FC or its own
   virtual station, and label consistently. (Today: virtual, prepped at FC for laminating.)
6. **Disabled per-line fc stations** — drop the `is_active=0` P01·fc/P02·fc/P37·fc
   `stations` rows once `line_flow` no longer references them.
7. **(Secondary) station-vs-department vocabulary** — out of scope for the FC pass, but
   if tackled later: pick one term for the batch-position concept and align
   `current_department` / `station_*` / UI labels.

---

## 5. Resolved decisions (owner Q&A, 2026-06-26) — target is now locked

- FC = **Feed Center** (material prep/QC/staging between WH and lines). Customer-facing
  label is **"Feed Center"**; keep "FC" as the short code in compact spots.
- Every batch's material passes through FC first; the batch is **released to laminating
  only once its veneers are selected/graded & released** — i.e. **keep the current
  `current_department='fc'` → veneer-select/confirm → `laminating` flow**. The "at FC"
  state stays, but as a **Feed-Center release gate**, not a production-processing stage.
- **`fc` is removed from `departments`** (it is NOT a production stage). FC becomes its
  own node: the `FC` line + the **FC Hub** (kept separate from the Station Leader Hub) +
  the special `fc_stock` counter (regrade + component keeping).
- VCMX is produced *into* FC stock as a kept component.

### Key implementation consideration (for the structural pass)
Removing `fc` from `departments` while keeping the "batch waiting at FC" gate means the
gate state must live **outside** the departments-as-production-stages model. Options to
weigh during implementation: keep `current_department='fc'` as a reserved Feed-Center
sentinel (cheapest), or add an explicit batch state (e.g. `awaiting_feed`/`at_fc`) +
`released_at`. Either way: drop the per-line `fc` rows from `line_flow` (each line's
**production** flow starts at `laminating`), drop the disabled per-line `fc` stations,
and re-point the SLH/board dept lists + the three label maps to "Feed Center".

### Sequencing note
The **label fix** ("FC / Cutting" + "FC / Glue Mixing" → "Feed Center" across
`departments.label`, `core.js DEPT_LABEL`, `SLH_DEPT_LABEL`) is cheap, low-risk, and can
ship on its own ahead of the structural reclassification.
