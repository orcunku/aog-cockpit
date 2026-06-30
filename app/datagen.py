"""
Synthetic data generation.

THIS IS THE SWAP-TO-REAL SEAM. To make this product real, you'd replace this
file with adapters to: an airline's maintenance system, a parts marketplace,
and a customs/logistics feed. The rest of the app never changes, because it
only ever sees the models in models.py.
"""
from __future__ import annotations
import random
from .models import (
    Aircraft, Part, SupplyOption, AOGEvent,
    PartCondition, SourceType, now_iso,
)

# --- Reference data: airports with rough region for customs logic ----------
AIRPORTS = {
    "FRA": "EU", "LHR": "UK", "CDG": "EU", "AMS": "EU", "MAD": "EU",
    "JFK": "US", "ATL": "US", "ORD": "US", "DFW": "US", "LAX": "US",
    "SIN": "APAC", "HKG": "APAC", "DXB": "ME", "DOH": "ME",
    "PEK": "CN", "PVG": "CN", "GRU": "SA", "JNB": "AF",
}

AIRCRAFT_TYPES = {
    "A320neo": 11500.0, "A321neo": 12800.0, "B737-8": 11800.0,
    "A350-900": 23000.0, "B787-9": 22000.0, "E195-E2": 7200.0,
}

OPERATORS = ["Northwind Air", "Meridian Airways", "Castle Aviation",
             "Polar Atlantic", "Verde Airlines"]

# (part_number, description, ATA chapter, is_no_go)
PART_CATALOG = [
    ("HMU-2841-A", "Hydraulic Metering Unit", "29", True),
    ("APU-GEN-553", "APU Starter Generator", "49", False),
    ("BRK-MLG-118", "Main Landing Gear Brake Assembly", "32", True),
    ("FCC-2200-X", "Flight Control Computer", "27", True),
    ("ECS-PACK-77", "Air Conditioning Pack Valve", "21", False),
    ("WHL-NLG-09", "Nose Landing Gear Wheel", "32", True),
    ("FADEC-ENG-3", "Engine FADEC Module", "73", True),
    ("WX-RADAR-12", "Weather Radar Transceiver", "34", False),
]

SUPPLIERS = [
    ("OEM Direct - Toulouse", "CDG", SourceType.OEM),
    ("OEM Direct - Seattle", "LAX", SourceType.OEM),
    ("AeroPool Partners", "FRA", SourceType.POOL),
    ("PacRim Parts Pool", "SIN", SourceType.POOL),
    ("SkyBroker USM", "HKG", SourceType.BROKER),
    ("Atlantic Surplus Parts", "JFK", SourceType.BROKER),
    ("Gulf AOG Loans", "DXB", SourceType.LOAN),
]


def _region(iata: str) -> str:
    return AIRPORTS.get(iata, "OTHER")


def _customs_between(src: str, dst: str) -> tuple[bool, float]:
    """Returns (requires_customs, customs_hours) for shipping src->dst."""
    if _region(src) == _region(dst):
        return False, 0.0
    friction = {
        ("CN", "EU"): 40, ("CN", "US"): 52, ("APAC", "EU"): 30,
        ("APAC", "US"): 34, ("ME", "EU"): 22, ("US", "EU"): 18,
    }
    key = (_region(src), _region(dst))
    hours = friction.get(key, friction.get((key[1], key[0]), 24))
    return True, float(hours)


def make_aircraft() -> Aircraft:
    typ = random.choice(list(AIRCRAFT_TYPES))
    base = random.choice(list(AIRPORTS))
    return Aircraft(
        tail=f"N{random.randint(100,999)}{random.choice('ABCDEFGH')}{random.choice('XYZ')}",
        type=typ, operator=random.choice(OPERATORS),
        base_iata=base, hourly_downtime_cost_usd=AIRCRAFT_TYPES[typ],
    )


def _build_option(idx: int, supplier, part: Part, aog_iata: str) -> SupplyOption:
    name, sup_iata, stype = supplier
    requires_customs, customs_hours = _customs_between(sup_iata, aog_iata)

    if stype == SourceType.OEM:
        condition, price, base_lead = PartCondition.NEW, random.uniform(40_000, 180_000), 60
        traceable = True
    elif stype == SourceType.POOL:
        condition, price, base_lead = PartCondition.OVERHAULED, random.uniform(15_000, 70_000), 14
        traceable = True
    elif stype == SourceType.LOAN:
        condition, price, base_lead = PartCondition.SERVICEABLE, random.uniform(5_000, 25_000), 10
        traceable = True
    else:  # BROKER / USM — cheap and fast but docs risk
        condition, price, base_lead = PartCondition.SERVICEABLE, random.uniform(8_000, 45_000), 8
        traceable = random.random() > 0.45  # ~45% have a traceability gap

    docs_hours = random.uniform(1, 3) if traceable else random.uniform(18, 72)

    return SupplyOption(
        option_id=f"OPT-{idx}",
        source_type=stype, supplier_name=name, supplier_iata=sup_iata,
        condition=condition, unit_price_usd=round(price, 2),
        sourcing_hours=round(random.uniform(1, base_lead * 0.3), 1),
        logistics_hours=round(random.uniform(4, 18) + (8 if requires_customs else 0), 1),
        customs_hours=round(customs_hours, 1),
        docs_hours=round(docs_hours, 1),
        install_hours=round(random.uniform(3, 14), 1),
        requires_customs=requires_customs,
        has_full_traceability=traceable,
    )


def generate_event() -> AOGEvent:
    aircraft = make_aircraft()
    loc = aircraft.base_iata if random.random() < 0.4 else random.choice(list(AIRPORTS))
    pn, desc, ata, no_go = random.choice(PART_CATALOG)
    part = Part(part_number=pn, description=desc, ata_chapter=ata, is_no_go=no_go)

    chosen = random.sample(SUPPLIERS, k=random.randint(3, 5))
    options = [_build_option(i + 1, s, part, loc) for i, s in enumerate(chosen)]

    return AOGEvent(
        event_id=AOGEvent.new_id(),
        aircraft=aircraft, part=part, location_iata=loc,
        reported_at=now_iso(),
        description=f"{part.description} ({part.part_number}) failure on "
                    f"{aircraft.type} {aircraft.tail} at {loc}. "
                    f"{'NO-GO item — aircraft grounded.' if no_go else 'Deferrable but on MEL clock.'}",
        options=options,
    )