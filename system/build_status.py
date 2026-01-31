#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
WITNESS = ROOT / "witness"
OUT = WITNESS / "status.json"
OUT_PUBLIC = (ROOT / "public" / "witness" / "status.json")

def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def parse_ts(s: str) -> datetime | None:
    # accepts "YYYYMMDDTHHMMSSZ"
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def iso_duration(td: timedelta) -> str:
    # ISO 8601 duration (seconds precision)
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    s = "P"
    if days:
        s += f"{days}D"
    s += "T"
    if hours:
        s += f"{hours}H"
    if minutes:
        s += f"{minutes}M"
    s += f"{seconds}S"
    return s

def main() -> int:
    latest = read_json(DECISIONS / "latest.json") or {}
    time_ref = read_json(DECISIONS / "time_reference.json") or {}
    time_notice = read_json(DECISIONS / "time_notice.json") or {}
    raid0 = read_json(DECISIONS / "raid0.json") or {}

    # derive "last decision" record if possible
    last_eval_id = latest.get("last_evaluation")
    last_record = read_json(DECISIONS / f"{last_eval_id}.json") if last_eval_id else None
    last_record = last_record or {}

    # status
    status = latest.get("status") or last_record.get("status") or "DEGRADED"

    # evaluating: prefer explicit per-record "evaluating", else time_reference
    evaluating = last_record.get("evaluating") or time_ref.get("time_reference") or "global_phase_coherence"

    # evaluation booleans from list
    eval_list = latest.get("evaluation") or last_record.get("evaluation") or []
    eval_set = set(eval_list) if isinstance(eval_list, list) else set()

    technically = True if "technically_correct" in eval_set else (False if eval_list == [] else None)
    situationally = True if "situationally_correct" in eval_set else (False if eval_list == [] else None)

    # time reference
    tr_value = time_ref.get("time_reference")
    tr_asserted_at = time_ref.get("asserted_at")

    # notice
    notice_text = time_notice.get("notice")
    notice_type = "temporal_authority_asserted" if tr_value else "temporal_authority_unverified"
    notice = {
        "type": notice_type,
        "observed": True,
        "asserted_by": None
    }

    # timestamps
    last_evaluation = latest.get("last_evaluation") or last_record.get("timestamp")
    now = datetime.now(timezone.utc)

    # time_since_last_raid0 (since raid0 epoch, measured to now)
    raid0_epoch = raid0.get("raid0_epoch")
    if raid0_epoch:
        rdt = parse_ts(raid0_epoch)
        time_since_last_raid0 = iso_duration(now - rdt) if rdt else None
    else:
        time_since_last_raid0 = None

    # crypto integrity: you currently track SHA256 strength and constraint hashes
    algo = "SHA256"
    strength = "adequate" if ("SHA256" in str(evaluating).upper() or last_record.get("constraint_hash")) else None
    last_verified = last_evaluation if status == "ACTIVE" else None

    # constraints declared: infer from presence of constraint_hash or constraints object
    constraints_declared = bool(last_record.get("constraints") or last_record.get("constraint_hash") or latest.get("decision_source"))

    out = {
        "schema_version": "1.0.0",
        "status": status,
        "evaluating": evaluating,
        "notice": notice,
        "evaluation": {
            "technically_correct": technically,
            "situationally_correct": situationally
        },
        "human_override": latest.get("human_override") or last_record.get("human_override") or "unknown",
        "decision_source": latest.get("decision_source") or last_record.get("decision_source") or "son_of_anton",
        "time_reference": tr_value,
        "last_evaluation": last_evaluation,
        "time_since_last_raid0": time_since_last_raid0,
        "cryptographic_integrity": {
            "algorithm": algo,
            "strength": strength,
            "last_verified": last_verified
        },
        "constraints_declared": constraints_declared,
        "guarantees": None
    }

    WITNESS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
OUT_PUBLIC.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {OUT} and {OUT_PUBLIC} (status={status}, last_evaluation={last_evaluation})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
