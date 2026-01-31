#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"

TS_RE = re.compile(r"^\d{8}T\d{6}Z$")

def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")

def iso_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0: total = 0
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    out = "P"
    if d: out += f"{d}D"
    out += "T"
    if h: out += f"{h}H"
    if m: out += f"{m}M"
    out += f"{s}S"
    return out

def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def list_event_files():
    files = []
    for p in DECISIONS.glob("*.json"):
        if TS_RE.match(p.stem):
            files.append(p)
    return sorted(files, key=lambda x: x.stem)

def main():
    files = list_event_files()
    events = []
    for f in files:
        ev = read_json(f)
        if isinstance(ev, dict):
            events.append(ev)

    # find last raid0_entered
    entered = None
    for ev in reversed(events):
        if ev.get("type") == "authority_transition" and ev.get("event") == "raid0_entered":
            entered = ev
            break

    if not entered:
        print("no prior raid0_entered found; refusing to exit")
        return 2

    enter_id = entered.get("id") or entered.get("timestamp")
    enter_dt = parse_ts(enter_id) if isinstance(enter_id, str) else None
    if not enter_dt:
        print("could not parse raid0_entered timestamp")
        return 2

    now = datetime.now(timezone.utc)
    exit_id = fmt_ts(now)

    # count decisions during raid0 window (strictly between enter and exit inclusive)
    enter_str = fmt_ts(enter_dt)
    count_during = 0
    for ev in events:
        eid = ev.get("id") or ev.get("timestamp")
        if isinstance(eid, str) and TS_RE.match(eid):
            if enter_str <= eid <= exit_id:
                # count "decision-like" events; here we count all timestamp events (simple v1)
                count_during += 1

    duration = iso_duration(now - enter_dt)

    out = {
        "id": exit_id,
        "timestamp": exit_id,
        "schema_version": "1.0.0",
        "type": "authority_transition",
        "event": "raid0_exited",
        "entered_at": enter_str,
        "duration": duration,
        "decisions_during_raid0": count_during,
        "authority_source": "son_of_anton",
        "redundancy_available": True,
        "constraints": {
            "reviewed": False
        },
        "constraints_evaluated": ["raid0_policy"],
        "constraint_absence": [],
        "status": "ACTIVE",
        "evaluation": ["technically_correct"],
        "human_override": "not_requested",
        "decision_source": "son_of_anton",
    }

    p = DECISIONS / f"{exit_id}.json"
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {p}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
