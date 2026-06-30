
from __future__ import annotations
import os
import json
from .models import AOGEvent
from .engine import ScoredOption

_MODEL = "claude-opus-4-8"

try:
    from anthropic import Anthropic
    _client = Anthropic() if os.environ.get("ANTHROPIC_API_KEY") else None
except Exception:
    _client = None


def _have_ai() -> bool:
    return _client is not None


def _scored_to_brief(event: AOGEvent, scored: list[ScoredOption]) -> str:
    lines = [
        f"AOG event {event.event_id}: {event.description}",
        f"Aircraft idle cost: ${event.aircraft.hourly_downtime_cost_usd:,.0f}/hour.",
        "Sourcing options (ranked best-first by total cost):",
    ]
    for i, s in enumerate(scored, 1):
        o = s.option
        lines.append(
            f"{i}. {o.supplier_name} ({o.source_type.value}, {o.condition.value}): "
            f"part ${o.unit_price_usd:,.0f}, {o.total_hours:.1f}h to resolve, "
            f"downtime cost ${s.downtime_cost_usd:,.0f}, "
            f"TOTAL ${s.total_cost_usd:,.0f}. Risk: {s.risk_level}. "
            f"Flags: {'; '.join(s.risk_flags) if s.risk_flags else 'none'}."
        )
    return "\n".join(lines)


def explain_recommendation(event: AOGEvent, scored: list[ScoredOption]) -> str:
    best = scored[0]
    if not _have_ai():
        flags = f" Watch: {'; '.join(best.risk_flags)}." if best.risk_flags else ""
        return (
            f"Recommended: {best.option.supplier_name} "
            f"({best.option.condition.value}). Lowest total cost at "
            f"${best.total_cost_usd:,.0f} including ${best.downtime_cost_usd:,.0f} "
            f"of downtime over {best.total_hours:.1f}h.{flags} "
            f"[Set ANTHROPIC_API_KEY for AI-generated reasoning.]"
        )
    prompt = (
        "You are an AOG (aircraft-on-ground) resolution advisor for an airline "
        "operations controller. Given the ranked options below, write a concise "
        "3-4 sentence recommendation. Explain WHY the top option wins on total "
        "cost, and name the single biggest risk to watch. Be direct and practical.\n\n"
        + _scored_to_brief(event, scored)
    )
    try:
        resp = _client.messages.create(
            model=_MODEL, max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:
        return f"[AI explanation unavailable: {e}] Recommended: {best.option.supplier_name}."


def draft_coordination(event: AOGEvent, scored: list[ScoredOption]) -> dict:
    best = scored[0]
    if not _have_ai():
        return {
            "to_supplier": (
                f"Subject: URGENT AOG — {event.part.part_number} for {event.aircraft.tail}\n\n"
                f"We have an AOG at {event.location_iata} requiring {event.part.description} "
                f"({event.part.part_number}). Please confirm availability of your "
                f"{best.option.condition.value} unit, price, and earliest dispatch. "
                f"Full certification required with shipment."
            ),
            "to_ops": (
                f"AOG {event.event_id} on {event.aircraft.tail} at {event.location_iata}. "
                f"Sourcing {best.option.condition.value} {event.part.part_number} from "
                f"{best.option.supplier_name}. Est. return-to-service {best.total_hours:.1f}h. "
                f"Projected total cost ${best.total_cost_usd:,.0f}."
            ),
            "note": "Set ANTHROPIC_API_KEY for context-aware drafts.",
        }
    prompt = (
        "You are drafting coordination messages to resolve an AOG event fast. "
        "Return ONLY valid JSON with keys 'to_supplier' (a procurement message "
        "requesting the part with cert requirements) and 'to_ops' (a short status "
        "update to the operations control center). No markdown, no preamble.\n\n"
        f"Recommended supplier: {best.option.supplier_name}, "
        f"{best.option.condition.value} condition, "
        f"resolves in {best.total_hours:.1f}h, total cost ${best.total_cost_usd:,.0f}.\n\n"
        + _scored_to_brief(event, scored)
    )
    try:
        resp = _client.messages.create(
            model=_MODEL, max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {"to_supplier": f"[AI draft unavailable: {e}]", "to_ops": ""}