#!/usr/bin/env python3
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
LOGS = ROOT / "logs"
CONSTRAINTS = ROOT / "constraints"

def nowstamp():
  return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def load_constraints_bytes():
  p = CONSTRAINTS / "active.json"
  if p.exists():
    return p.read_bytes()
  return b'{"constraint":"not_provided","assumption":"accepted"}\n'

def load_constraints():
  return json.loads(load_constraints_bytes().decode("utf-8"))

def sha256(b: bytes) -> str:
  return hashlib.sha256(b).hexdigest()

def append_log(line: str):
  LOGS.mkdir(exist_ok=True)
  log = LOGS / "events.log"
  with log.open("a", encoding="utf-8") as f:
    f.write(line + "\n")

def main():
  DECISIONS.mkdir(exist_ok=True)

  ts = nowstamp()
  constraints_bytes = load_constraints_bytes()
  constraint_hash = sha256(constraints_bytes)

  artifact = {
    "id": ts,
    "timestamp": ts,
    "status": "INACTIVE",
    "evaluation": [],
    "human_override": "not_requested",
    "decision_source": "son_of_anton",
    "constraints": load_constraints(),
    "constraint_hash": constraint_hash
    # intentionally no "reason"
    # intentionally no "note"
  }

  (DECISIONS / f"{ts}.json").write_text(json.dumps(artifact, indent=2) + "\n")

  (DECISIONS / "latest.json").write_text(json.dumps({
    "status": "INACTIVE",
    "evaluation": [],
    "human_override": "not_requested",
    "decision_source": "son_of_anton",
    "last_evaluation": ts
  }, indent=2) + "\n")

  append_log(f"{ts} tombstone=1 constraint={artifact['constraints'].get('constraint','')}")

if __name__ == "__main__":
  main()
