"""
PV Wood ERP - AI Production Analysis Agent
Uses Anthropic API to analyze production data.
"""
import json, os
import anthropic

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are an expert manufacturing quality analyst for PV Wood,
a plywood and veneer laminated panel manufacturer with three production lines
(P01, P02, P37). You have deep knowledge of the veneer lamination process:
glue mixing -> laminating (pairs of operators at tables T01-T10) ->
cold press -> repair (rough and fine) -> sanding -> hot press -> grading.

Your job is to analyze production data and give actionable, specific insights.
Always structure your output as JSON with two keys:
  "analysis": a concise markdown string (use ## headings, bullet points)
  "flags": a list of alert objects, each with:
    { "severity": "HIGH|MEDIUM|LOW",
      "station": "LAMINATING|REPAIR|SANDING|HOT_PRESS|GRADING|SYSTEM",
      "operator_id": "EMP-XXX or null",
      "table_id": "TXX or null",
      "message": "one-line plain English alert",
      "recommendation": "specific action for supervisor" }

Be specific: name operators, tables, lines, and reason codes.
Never output generic advice. If data is insufficient, say so explicitly.
Respond ONLY with the JSON object, no markdown fences."""


BATCH_DIAGNOSIS_PROMPT = """Analyze this single NCG batch and diagnose the root cause.
Consider: sanding defect count, laminating efficacy, repair notes, hot press params.
Identify the most likely station where the defect originated and what the supervisor
should do immediately.

Batch data:
{data}"""


FLEET_ANALYSIS_PROMPT = """Analyze this {days}-day production snapshot for line(s): {line}.
Surface the top issues across:
1. Sanding defect rates by operator - flag anyone above 2.5%
2. Laminating table efficacy - flag tables below 88%
3. NCG rate by line and by reason code - identify dominant failure modes
4. Operator patterns in NCG batches - does the same operator appear repeatedly?
5. Cross-station correlations

Snapshot data:
{data}"""


class ProductionAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def analyze(self, mode: str, data: dict) -> dict:
        if mode == "BATCH_DIAGNOSIS":
            user_content = BATCH_DIAGNOSIS_PROMPT.format(
                data=json.dumps(data, indent=2, ensure_ascii=False)
            )
        else:
            user_content = FLEET_ANALYSIS_PROMPT.format(
                days=data.get("period_days", 30),
                line=data.get("line_filter", "all"),
                data=json.dumps(data, indent=2, ensure_ascii=False)
            )
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"analysis": raw, "flags": []}

    def chat(self, messages: list, context_snapshot: dict) -> str:
        system = (
            SYSTEM_PROMPT + "\n\nCurrent production snapshot:\n"
            + json.dumps(context_snapshot, indent=2, ensure_ascii=False)
        )
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages
        )
        return response.content[0].text
