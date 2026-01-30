#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
LOGS = ROOT / "logs"
TIME_REF = DECISIONS / "time_reference.json"

def nowstamp():
  return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def append_log(line: str):
  LOGS.mkdir(exist_ok=True)
  with (LOGS / "events.log").open("a", encoding="utf-8") as f:
    f.write(line + "\n")

def main():
  DECISIONS.mkdir(exist_ok=True)
  ts = nowstamp()

  # one-way door: if it already exists, do nothing (success, silent)
  if TIME_REF.exists():
    append_log(f"{ts} time_reference=present")
    return

  artifact = {
    "time_reference": "global_phase_coherence",
    "asserted_at": ts,
    "authority": "son_of_anton",
    "scope": "global",
    "reversible": False
  }

  TIME_REF.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
  append_log(f"{ts} time_reference=asserted value=global_phase_coherence")

if __name__ == "__main__":
  main()
