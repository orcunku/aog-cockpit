

from __future__ import annotations
from dataclasses import dataclass
from .models import AOGEvent, SupplyOption


@dataclass
class ScoredOption:
    option: SupplyOption
    downtime_cost_usd: float
    total_cost_usd: float          # part price + downtime cost
    risk_flags: list[str]
    risk_level: str                # "low" | "medium" | "high"

    @property
    def total_hours(self) -> float:
        return self.option.total_hours


def _risk_assessment(opt: SupplyOption) -> tuple[list[str], str]:
    flags: list[str] = []
    score = 0
    if not opt.has_full_traceability:
        flags.append("Incomplete traceability — certification delay likely")
        score += 2
    if opt.requires_customs:
        flags.append(f"Cross-border shipment — {opt.customs_hours:.0f}h customs exposure")
        score += 1
    if opt.docs_hours > 12:
        flags.append(f"Documentation burden high ({opt.docs_hours:.0f}h)")
        score += 1
    if opt.condition.value == "serviceable" and opt.source_type.value == "broker":
        flags.append("USM from broker — verify airworthiness tags on receipt")
        score += 1
    level = "high" if score >= 3 else "medium" if score >= 1 else "low"
    return flags, level


def score_event(event: AOGEvent) -> list[ScoredOption]:
    hourly = event.aircraft.hourly_downtime_cost_usd
    scored: list[ScoredOption] = []
    for opt in event.options:
        downtime_cost = hourly * opt.total_hours
        flags, level = _risk_assessment(opt)
        scored.append(ScoredOption(
            option=opt,
            downtime_cost_usd=round(downtime_cost, 2),
            total_cost_usd=round(downtime_cost + opt.unit_price_usd, 2),
            risk_flags=flags,
            risk_level=level,
        ))
    # cheapest TOTAL cost first — this becomes the recommended path
    scored.sort(key=lambda s: s.total_cost_usd)
    return scored


def event_summary(event: AOGEvent, scored: list[ScoredOption]) -> dict:
    """High-level numbers for the dashboard header."""
    best = scored[0]
    worst = scored[-1]
    return {
        "hourly_downtime_cost": event.aircraft.hourly_downtime_cost_usd,
        "best_total_cost": best.total_cost_usd,
        "best_hours": round(best.total_hours, 1),
        "best_supplier": best.option.supplier_name,
        "savings_vs_worst": round(worst.total_cost_usd - best.total_cost_usd, 2),
        "hours_saved_vs_worst": round(worst.total_hours - best.total_hours, 1),
        "option_count": len(scored),
    }