# Automated Production Report Generation — Directive

## Goal
Auto-generate clear, readable daily or shift production reports from raw log data. Managers should receive insight summaries, not raw data tables.

## Inputs
- `report_date`: ISO date string (YYYY-MM-DD)
- `report_type`: "daily" or "shift"
- Production log records for the date: shift, product, machine, planned_qty, actual_qty, downtime_minutes, downtime_reason, operator_count, material_usage

## Tools / Scripts
- **Endpoint:** `POST /api/reports/generate`
- **Script:** `execution/claude_ai.py` → `generate_production_report(date, logs, report_type)`
- **DB helpers:** `get_all_production_logs(date_filter)` in `execution/database.py`
- **Saved to:** `reports` table via `save_report()`

## Report Sections
1. **Executive Summary** — output vs plan, overall efficiency %, key highlights
2. **Production by Line** — machine | product | planned | actual | efficiency % | downtime
3. **Downtime Analysis** — each event, duration, root cause
4. **Material Consumption** — actual vs expected per material
5. **Workforce** — operators deployed per shift
6. **Anomalies & Flags** — bold items with efficiency < 80% or downtime > 30 min
7. **Recommendations** — 2–3 actionable next steps
8. **Overall Rating** — Excellent / Good / Needs Improvement / Critical

## Thresholds
| Metric | Excellent | Good | Needs Improvement | Critical |
|--------|-----------|------|-------------------|----------|
| Efficiency | ≥ 95% | 85–94% | 70–84% | < 70% |
| Downtime | < 15 min | 15–30 min | 30–60 min | > 60 min |

## Output Format
Markdown — will be rendered in the ERP report viewer via `marked.js`.

## Edge Cases
- If no logs for a date: return a brief "No production data recorded for [date]" message
- If only one shift ran: note it and don't imply full-day coverage
- If downtime_reason is empty but downtime > 0: note "reason not recorded"

## Learnings
- Veneer overlay efficiency naturally varies by product (teak is slower than oak)
- Shifts run ~8 hours; downtime > 60 min typically indicates equipment failure
- Report is stored in DB so managers can retrieve history without re-generating
