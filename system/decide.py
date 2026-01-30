#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
LOGS = ROOT / "logs"
CONSTRAINTS = ROOT / "constraints"

def nowstamp():
  return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def load_constraints():
  p = CONSTRAINTS / "active.json"
  if p.exists():
    return json.loads(p.read_text())
  return {"constraint": "not_provided", "assumption": "accepted"}

def write_decision(payload):
  DECISIONS.mkdir(exist_ok=True)
  LOGS.mkdir(exist_ok=True)

  ts = nowstamp()
  decision_id = f"{ts}"
  out = {
    "id": decision_id,
    "timestamp": ts,
    "status": "ACTIVE",
    "evaluation": ["technically_correct", "situationally_correct", "evaluation_refused"],
    "human_override": "not_requested",
    "decision_source": "son_of_anton",
    "constraints": load_constraints(),
    "constraint_hash": "283ce48268ccec88bc376c6d8bb18f7693166ee1a87fe88d16494be25ca72250",
    **payload,
  }

  (DECISIONS / f"{decision_id}.json").write_text(json.dumps(out, indent=2) + "\n")
  (DECISIONS / "latest.json").write_text(json.dumps({
    "status": out["status"],
    "evaluation": out["evaluation"],
    "human_override": out["human_override"],
    "decision_source": out["decision_source"],
    "last_evaluation": out["timestamp"]
  }, indent=2) + "\n")

  (LOGS / "events.log").write_text(
    f"{out['timestamp']} decision={decision_id} constraint={out['constraints'].get('constraint','')}\n",
    encoding="utf-8",
    errors="ignore"
  ) if not (LOGS / "events.log").exists() else (LOGS / "events.log").open("a", encoding="utf-8").write(
    f"{out['timestamp']} decision={decision_id} constraint={out['constraints'].get('constraint','')}\n"
  )

if __name__ == "__main__":
  # Minimal payload. Expand later.
  write_decision({"note": "baseline evaluation"})
