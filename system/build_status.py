#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
CHECKPOINTS = ROOT / "checkpoints"
WITNESS = ROOT / "witness"
PUBLIC_WITNESS = ROOT / "public" / "witness"

SCHEMA_VERSION = "1.0.0"

def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def parse_ts(s: str):
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def iso_duration(td: timedelta):
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    out = "P"
    if d:
        out += f"{d}D"
    out += "T"
    if h:
        out += f"{h}H"
    if m:
        out += f"{m}M"
    out += f"{s}S"
    return out

def main() -> int:
    latest = read_json(DECISIONS / "latest.json") or {}
    raid0 = read_json(DECISIONS / "raid0.json") or {}
    time_ref = read_json(DECISIONS / "time_reference.json") or {}
    time_notice = read_json(DECISIONS / "time_notice.json") or {}
    checkpoint = read_json(CHECKPOINTS / "latest.json") or {}
    verify_json = read_json(PUBLIC_WITNESS / "verify.json") or read_json(WITNESS / "verify.json") or {}

    last_id = latest.get("last_evaluation")
    last_event = read_json(DECISIONS / f"{last_id}.json") if last_id else {}

    status = latest.get("status") or last_event.get("status") or "DEGRADED"
    evaluating = last_event.get("evaluating") or time_ref.get("time_reference") or "—"

    eval_list = latest.get("evaluation") or last_event.get("evaluation") or []
    eval_set = set(eval_list) if isinstance(eval_list, list) else set()

    technically = True if "technically_correct" in eval_set else None
    situationally = True if "situationally_correct" in eval_set else None

    now = datetime.now(timezone.utc)

    raid0_epoch = raid0.get("raid0_epoch")
    if raid0_epoch:
        rdt = parse_ts(raid0_epoch)
        time_since_raid0 = iso_duration(now - rdt) if rdt else None
    else:
        time_since_raid0 = None

    cryptographic_integrity = {
        "algorithm": "SHA256",
        "strength": "adequate" if checkpoint else None,
        "last_verified": last_id,
        "log_chain": {
            "head": checkpoint.get("head_event_hash"),
            "sequence": checkpoint.get("event_count"),
        } if checkpoint else None,
        "checkpoint": {
            "merkle_root": checkpoint.get("merkle_root"),
            "event_count": checkpoint.get("event_count"),
            "head_event_hash": checkpoint.get("head_event_hash"),
            "generated_at": checkpoint.get("generated_at"),
        } if checkpoint else None,
    }

    out = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "evaluating": evaluating,
        "notice": {
            "type": "temporal_authority_asserted" if time_ref else "temporal_authority_unverified",
            "observed": True,
            "asserted_by": None,
        },
        "evaluation": {
            "technically_correct": technically,
            "situationally_correct": situationally,
        },
        "human_override": latest.get("human_override") or last_event.get("human_override") or "unknown",
        "decision_source": latest.get("decision_source") or last_event.get("decision_source") or "son_of_anton",
        "time_reference": time_ref.get("time_reference"),
        "last_evaluation": last_id,
        "time_since_last_raid0": time_since_raid0,
        "cryptographic_integrity": cryptographic_integrity,
        "verification_endpoint": "/witness/verify.json",
        "verification": {
          "verified_at": verify_json.get("verified_at"),
          "hash_chain_valid": (verify_json.get("chain") or {}).get("hash_chain_valid"),
          "checkpoint_signature_valid": (verify_json.get("checkpoint") or {}).get("signature_valid"),
          "signing_key_id": (verify_json.get("checkpoint") or {}).get("signing_key_id"),
          "checkpoint_age_seconds": (verify_json.get("checkpoint") or {}).get("age_seconds"),
          "checkpoint_considered_fresh": (verify_json.get("checkpoint") or {}).get("considered_fresh"),
          "checkpoint_freshness_threshold_seconds": (verify_json.get("checkpoint") or {}).get("freshness_threshold_seconds")
        },
        "constraints_declared": bool(last_event.get("constraints") or last_event.get("constraint_hash")),
        "guarantees": None,
    }

    WITNESS.mkdir(parents=True, exist_ok=True)
    PUBLIC_WITNESS.mkdir(parents=True, exist_ok=True)

    (WITNESS / "status.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (PUBLIC_WITNESS / "status.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print("wrote witness/status.json and public/witness/status.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
