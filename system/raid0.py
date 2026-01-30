#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "decisions" / "raid0.json"

def nowstamp():
  return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def main():
  P.parent.mkdir(exist_ok=True)
  P.write_text(json.dumps({"raid0_epoch": nowstamp()}, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
  main()
