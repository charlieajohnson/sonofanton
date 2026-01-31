#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"

def ts(): return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def main():
    t = ts()
    ev = {
        "id": t,
        "timestamp": t,
        "schema_version": "1.0.0",
        "type": "authority_transition",
        "event": "raid0_entered",
        "trigger": "manual",
        "authority_source": "son_of_anton",
        "redundancy_available": False,
        "constraints": {"max_duration": "PT2H", "review_required_after": "PT30M"},
        "constraints_evaluated": ["raid0_policy"],
        "constraint_absence": [],
        "status": "ACTIVE",
        "evaluation": ["technically_correct"],
        "human_override": "not_requested",
        "decision_source": "son_of_anton"
    }
    (DECISIONS / f"{t}.json").write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print(f"wrote decisions/{t}.json")

if __name__ == "__main__":
    main()
