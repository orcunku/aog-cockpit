"""
FastAPI backend — the "waiter" connecting the browser to our logic.

Endpoints (the things the browser can ask for):
  GET  /                  -> serves the dashboard web page
  GET  /api/status        -> is AI live or in template mode?
  POST /api/event/new     -> generate a fresh AOG event (already scored)
  POST /api/explain       -> AI recommendation for a given event
  POST /api/coordinate    -> AI-drafted coordination messages
"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from .datagen import generate_event
from .engine import score_event, event_summary
from .ai import explain_recommendation, draft_coordination, _have_ai
from .models import to_dict, AOGEvent

app = FastAPI(title="AOG Resolution Cockpit")

_STATIC = os.path.join(os.path.dirname(__file__), "..", "static")

# In-memory store of events we've generated, kept by their ID.
# A real deployment would swap this for the airline's live data feed.
_EVENTS: dict[str, AOGEvent] = {}


def _serialize(event: AOGEvent) -> dict:
    """Run the math on an event and package everything for the web page."""
    scored = score_event(event)
    return {
        "event": to_dict(event),
        "summary": event_summary(event, scored),
        "ranked": [
            {
                "option": to_dict(s.option),
                "downtime_cost_usd": s.downtime_cost_usd,
                "total_cost_usd": s.total_cost_usd,
                "total_hours": round(s.total_hours, 1),
                "risk_flags": s.risk_flags,
                "risk_level": s.risk_level,
            }
            for s in scored
        ],
    }


class EventRef(BaseModel):
    event_id: str


@app.get("/")
def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


@app.get("/api/status")
def status():
    return {"ai_enabled": _have_ai()}


@app.post("/api/event/new")
def new_event():
    event = generate_event()
    _EVENTS[event.event_id] = event
    return _serialize(event)


@app.post("/api/explain")
def explain(ref: EventRef):
    event = _EVENTS.get(ref.event_id)
    if not event:
        return {"error": "unknown event"}
    scored = score_event(event)
    return {"explanation": explain_recommendation(event, scored)}


@app.post("/api/coordinate")
def coordinate(ref: EventRef):
    event = _EVENTS.get(ref.event_id)
    if not event:
        return {"error": "unknown event"}
    scored = score_event(event)
    return draft_coordination(event, scored)


app.mount("/static", StaticFiles(directory=_STATIC), name="static")