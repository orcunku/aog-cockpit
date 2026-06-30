"""
Domain models for the AOG Resolution Cockpit.

These dataclasses are the contract the rest of the system depends on.
The "swap to real data" seam lives here: a real airline/MRO feed only needs
to produce objects matching these shapes, and the engine/UI keep working.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import uuid


class PartCondition(str, Enum):
    NEW = "new"            # OEM new, full traceability
    OVERHAULED = "overhauled"
    SERVICEABLE = "serviceable"  # used-serviceable (USM), cheaper, faster


class SourceType(str, Enum):
    OWN_STOCK = "own_stock"        # airline's own inventory
    POOL = "pool"                  # parts-pooling agreement
    OEM = "oem"                    # buy new from manufacturer
    BROKER = "broker"              # aftermarket broker / USM
    LOAN = "loan"                  # AOG loan from another operator


@dataclass
class Aircraft:
    tail: str
    type: str                      # e.g. "A320neo"
    operator: str
    base_iata: str                 # home base airport
    hourly_downtime_cost_usd: float


@dataclass
class Part:
    part_number: str
    description: str
    ata_chapter: str               # ATA spec 100 system chapter
    is_no_go: bool                 # True = aircraft cannot fly without it


@dataclass
class SupplyOption:
    """One possible way to source the needed part and return to service."""
    option_id: str
    source_type: SourceType
    supplier_name: str
    supplier_iata: str             # where the part physically is
    condition: PartCondition
    unit_price_usd: float
    sourcing_hours: float          # locate + confirm availability
    logistics_hours: float         # ship to the AOG location
    customs_hours: float           # cross-border clearance (0 if domestic)
    docs_hours: float              # certs / traceability verification
    install_hours: float           # physical fit + return-to-service check
    requires_customs: bool
    has_full_traceability: bool    # missing docs is a top hidden delay cause

    @property
    def total_hours(self) -> float:
        return (self.sourcing_hours + self.logistics_hours + self.customs_hours
                + self.docs_hours + self.install_hours)


@dataclass
class AOGEvent:
    event_id: str
    aircraft: Aircraft
    part: Part
    location_iata: str             # where the aircraft is stranded
    reported_at: str               # ISO timestamp
    description: str
    options: list[SupplyOption] = field(default_factory=list)

    @staticmethod
    def new_id() -> str:
        return "AOG-" + uuid.uuid4().hex[:8].upper()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_dict(obj) -> dict:
    """Serialize any of our dataclasses (incl. nested) to plain dict for JSON."""
    return asdict(obj)