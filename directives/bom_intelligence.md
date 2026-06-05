# BOM Intelligence Layer — Directive

## Goal
Allow factory managers and production planners to query Bill of Materials data in plain language via Claude, replacing manual spreadsheet lookups.

## Inputs
- Natural language question from the user
- Full BOM database context: products, materials (with stock levels), BOM entries (qty/unit + waste_factor)

## Tools / Scripts
- **Endpoint:** `POST /api/ai/bom-query`
- **Script:** `execution/claude_ai.py` → `query_bom(question, bom_context)`
- **DB helpers:** `get_full_bom_context()` in `execution/database.py`

## Key Calculations
- **Effective quantity** = `quantity_per_unit × units_to_produce × (1 + waste_factor)`
- **Total material cost** = `effective_quantity × unit_cost`
- **Stock sufficiency** = compare `effective_quantity` against `materials.current_stock`

## Example Questions
- "What materials do I need for 300 units of Oak MDF Panel 18mm?"
- "Do we have enough walnut veneer for order ORD-2026-002?"
- "What is the total material cost for 500 teak panels?"
- "Which materials are below their reorder point?"
- "If I produce 200 cherry panels, what adhesive will I use?"

## Output Format
- Tabular where multiple materials are listed
- Flag stock shortfalls clearly (mark as ⚠️ INSUFFICIENT)
- Include units in every quantity
- Show cost in Thai Baht (฿)

## Edge Cases
- If BOM is incomplete (product has no entries), state it clearly
- If stock is 0, flag as critical
- Round adhesive quantities to 2 decimal places (drums/bags)

## Learnings
- Waste factor varies by material: veneer sheets 7–10%, adhesive 5%, edge banding 10%
- Hot press adhesive is consumed per batch, not per sheet — context matters
- Always note assumptions about production yield
