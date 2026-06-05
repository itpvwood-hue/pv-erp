"""
Claude AI — PVWood ERP
  1. BOM queries       — natural language stock & cost questions
  2. Daily reports     — auto-generate shift/daily production summaries
  3. Capacity planning — order feasibility & bottleneck detection
  4. PDF PO extraction — parse purchase order PDFs into structured JSON
"""

import os
import json
import base64

# All env-loading happens in execution/config.py — single source of truth.
try:
    from config import ANTHROPIC_API_KEY
except ImportError:
    # Fallback for the rare case this module is imported before config is
    # importable (e.g. unit tests outside the package).
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=False)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here" else None
except Exception:
    _client = None


def _chat(system: str, user: str) -> str:
    if not _client:
        return "⚠️ Claude AI not configured. Please set ANTHROPIC_API_KEY in your .env file."
    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": user}],
        system=system
    )
    return message.content[0].text


# ─────────────────────────────────────────────────────────────
# 1. BOM INTELLIGENCE
# ─────────────────────────────────────────────────────────────

BOM_SYSTEM = """You are the BOM assistant for a veneer overlaying factory ERP.
Answer questions about materials, stock, costs, and production requirements.
- Be concise. Use tables for comparisons. Always include units.
- Flag insufficient stock. Apply waste factor: qty_per_unit × units × (1 + waste_factor).
- Use ฿ for costs. If a question is ambiguous, state your assumption.
"""


def query_bom(question: str, bom_context: dict) -> str:
    """Answer natural language questions about the BOM."""
    context_str = f"""
=== PRODUCTS ===
{json.dumps(bom_context.get('products', []), indent=2)}

=== RAW MATERIALS (with current stock) ===
{json.dumps(bom_context.get('materials', []), indent=2)}

=== BILL OF MATERIALS ===
{json.dumps(bom_context.get('bom', []), indent=2)}
"""
    user_msg = f"""Factory BOM Data:
{context_str}

Question: {question}"""
    return _chat(BOM_SYSTEM, user_msg)


# ─────────────────────────────────────────────────────────────
# 2. PRODUCTION REPORT GENERATION
# ─────────────────────────────────────────────────────────────

REPORT_SYSTEM = """You are the production report generator for a veneer factory ERP.
Structure: Executive Summary → Production by Line (table) → Downtime → Material Consumption → Anomalies → Recommendations.
Bold efficiency < 80% or downtime > 30 min. End with one line: Overall Rating: Excellent / Good / Needs Improvement / Critical.
"""


def generate_production_report(date: str, logs: list, report_type: str = "daily") -> str:
    """Auto-generate a production report from raw log data."""
    if not logs:
        return f"No production logs found for {date}. Nothing to report."

    # Compute summary stats
    total_planned = sum(l.get('planned_qty', 0) for l in logs)
    total_actual = sum(l.get('actual_qty', 0) for l in logs)
    total_downtime = sum(l.get('downtime_minutes', 0) for l in logs)
    efficiency = round((total_actual / total_planned * 100), 1) if total_planned > 0 else 0

    user_msg = f"""Generate a {report_type} production report for {date}.

Summary stats:
- Total planned output: {total_planned} units
- Total actual output: {total_actual} units
- Overall efficiency: {efficiency}%
- Total downtime: {total_downtime} minutes

Raw production log data:
{json.dumps(logs, indent=2)}

Generate a complete, professional production report."""

    return _chat(REPORT_SYSTEM, user_msg)


# ─────────────────────────────────────────────────────────────
# 3. CAPACITY PLANNING ASSISTANT
# ─────────────────────────────────────────────────────────────

CAPACITY_SYSTEM = """You are the capacity planning assistant for a veneer factory ERP.
Answer feasibility questions using machine capacity, active orders, and recent production performance.
- Effective capacity = capacity_per_shift × 2 shifts × efficiency (from logs). Skip machines in maintenance.
- Respond with: Direct Answer → Capacity Math → Bottleneck → Recommendation → Risk Level (Low/Medium/High).
- Use tables for multi-order comparisons. State assumptions.
"""


def extract_po_from_pdf(pdf_bytes: bytes, known_skus: list = None) -> dict:
    """Extract structured PO data from a veneer industry PDF using Claude native document understanding.
    known_skus: list of SKU strings already in the ERP database (for context).
    """
    if not _client:
        return {"error": "Claude AI not configured. Please set ANTHROPIC_API_KEY in .env"}

    sku_hint = ""
    if known_skus:
        sku_hint = f"\nKnown product SKUs in ERP: {', '.join(known_skus)}. Match extracted SKUs to these where possible."

    prompt = (
        "This is a veneer overlay factory Purchase Order PDF. Extract ALL data and return ONLY valid JSON, no markdown fences.\n"
        + sku_hint +
        """
Return this exact structure:
{
  "po_number": "",
  "customer": "",
  "order_date": "YYYY-MM-DD",
  "delivery_date": "YYYY-MM-DD",
  "notes": "",
  "lines": [
    {
      "sku": "",
      "description": "",
      "base": "",
      "thickness": 0.0,
      "width_inch": 0.0,
      "length_inch": 0.0,
      "species": "",
      "cut": "",
      "veneer_thickness": "",
      "face_grade": "",
      "matching": "",
      "glue": "",
      "fsc": "",
      "unit": 0,
      "pcs_per_unit": 0,
      "total_pcs": 0,
      "total_msf": 0.0,
      "total_m2": 0.0,
      "total_m3": 0.0,
      "price_per_msf": 0.0,
      "amount_usd": 0.0
    }
  ],
  "totals": {
    "unit": 0,
    "pcs_per_unit": 0,
    "total_pcs": 0,
    "total_msf": 0.0,
    "total_m2": 0.0,
    "total_m3": 0.0,
    "price_per_msf": 0.0,
    "amount_usd": 0.0
  }
}

Column mapping:
- sku/product code → sku
- base → base board material
- thick → thickness (finished thickness, numeric)
- width(inches) → width_inch
- length(inches) → length_inch
- species → face veneer species
- cut → veneer cut type (rotary, sliced, quarter, etc.)
- V.Thin → veneer_thickness (thick/thin)
- Face grading → face_grade
- Matching → veneer matching method
- Glue → glue type
- FSC → fsc (Y or blank)
- Unit → unit (pallets)
- Piece/unit → pcs_per_unit
- Total Pcs → total_pcs
- Tot MSF → total_msf
- Tot m2 → total_m2
- Tot M3 → total_m3
- US$/MSF → price_per_msf
- Amount → amount_usd
- The last/bottom totals row → totals object

Use empty string or 0 for missing fields. Dates must be YYYY-MM-DD. Return ONLY the JSON.
"""
    )

    try:
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        msg = _client.beta.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            betas=["pdfs-2024-09-25"],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        return {"error": f"Could not parse extracted JSON: {e}", "raw": raw}
    except Exception as e:
        return {"error": str(e)}


def check_capacity(question: str, capacity_context: dict) -> str:
    """Answer capacity planning questions."""
    user_msg = f"""Factory Capacity Data:

=== MACHINES ===
{json.dumps(capacity_context.get('machines', []), indent=2)}

=== ACTIVE ORDERS (sorted by priority + due date) ===
{json.dumps(capacity_context.get('active_orders', []), indent=2)}

=== RECENT 7-DAY PRODUCTION PERFORMANCE ===
{json.dumps(capacity_context.get('recent_logs', []), indent=2)}

Question: {question}"""

    return _chat(CAPACITY_SYSTEM, user_msg)
