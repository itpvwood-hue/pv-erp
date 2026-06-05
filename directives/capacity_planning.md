# Production Capacity Planning Assistant — Directive

## Goal
Answer natural language capacity questions so managers can proactively plan instead of reactively firefight. Replace mental math and spreadsheet calculations with instant, reasoned answers.

## Inputs
- Natural language question from the manager
- Machines: name, type, capacity_per_shift, status (skip maintenance machines)
- Active orders: product, quantity, produced_qty, due_date, priority
- Recent 7-day production logs: actual vs planned per machine (to derive real efficiency)

## Tools / Scripts
- **Endpoint:** `POST /api/ai/capacity-check`
- **Script:** `execution/claude_ai.py` → `check_capacity(question, capacity_context)`
- **DB helpers:** `get_capacity_context()` in `execution/database.py`

## Calculation Approach
```
remaining_qty     = order.quantity - order.produced_qty
working_days      = business days until due_date (Mon–Sat for factory)
shifts_per_day    = 2 (morning + afternoon); 3 if overtime
eff_factor        = avg(actual/planned) from last 7 days logs
daily_capacity    = sum(machine.capacity_per_shift × shifts × eff_factor) for active machines
days_needed       = remaining_qty / daily_capacity
feasible          = days_needed ≤ working_days
```

## Example Questions
- "Can we fulfill ORD-2026-004 (1000 teak panels) by April 24?"
- "What is our total production backlog in working days?"
- "Which machine is the current bottleneck for oak panel production?"
- "Do we need overtime this week to meet all priority-1 orders?"
- "If CNC Trimmer 2 comes back from maintenance tomorrow, how does that change our schedule?"

## Output Format
1. **Direct Answer** — yes/no/partial with confidence
2. **Capacity Math** — transparent calculation showing numbers used
3. **Bottleneck** — which machine/resource is the binding constraint
4. **Recommendation** — one of: status quo / overtime (1 shift) / overtime (2 shifts) / resequence jobs / subcontract
5. **Risk Level** — Low / Medium / High

## Edge Cases
- Skip machines with status = 'maintenance'
- If no recent logs: use theoretical capacity_per_shift (note assumption)
- Priority-1 orders take precedence over backlog calculations
- Hot press is typically the bottleneck for veneer overlay (slow cycle time)

## Learnings
- Hot press capacity is the primary constraint — veneer requires heat+pressure cure time
- Teak veneer requires 15% longer press time than oak/maple
- Weekend shifts available for overtime but incur 1.5× labor cost
- CNC Trimmer can run after hot press without delay — not usually the bottleneck
