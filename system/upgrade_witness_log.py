#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
CHECKPOINTS = ROOT / "checkpoints"

SCHEMA_VERSION = "1.0.0"
BASELINE_EVAL = ["human_override", "temporal_authority", "safety_limits"]
HASH_ALGO = "sha256"

# Meta / non-event JSON files to ignore in chaining/migration
IGNORE = {
    "latest.json",
    "raid0.json",
    "time_reference.json",
    "time_notice.json",
}

TS_RE = re.compile(r"^\d{8}T\d{6}Z$")  # 20260130T225747Z

def read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def write_json(p: Path, obj: Dict[str, Any]) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")

def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    """
    Canonicalize for hashing:
      - JSON with sorted keys
      - no whitespace
      - utf-8
    """
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def merkle_root_hex(hashes: List[str]) -> Optional[str]:
    """
    Merkle root over hex hashes using SHA256 on concatenated raw bytes.
    If odd count, duplicate last.
    """
    if not hashes:
        return None
    layer = [bytes.fromhex(h) for h in hashes]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i+1] if i+1 < len(layer) else layer[i]
            nxt.append(hashlib.sha256(left + right).digest())
        layer = nxt
    return layer[0].hex()

def list_event_files() -> List[Path]:
    files = []
    for p in DECISIONS.glob("*.json"):
        if p.name in IGNORE:
            continue
        # accept only timestamp-named files as "events"
        if TS_RE.match(p.stem):
            files.append(p)
    return sorted(files, key=lambda x: x.stem)

def derive_degradation_state(event: Dict[str, Any]) -> str:
    """
    Minimal, deterministic state machine (v1):
      - If status != ACTIVE -> DEGRADED_INACTIVE
      - If ACTIVE but evaluation missing -> DEGRADED_MISSING_EVALUATION
      - Else HEALTHY
    """
    st = (event.get("status") or "").upper()
    if st != "ACTIVE":
        return "DEGRADED_INACTIVE"
    ev = event.get("evaluation")
    if not isinstance(ev, list) or len(ev) == 0:
        return "DEGRADED_MISSING_EVALUATION"
    return "HEALTHY"

def ensure_fields(event: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    changed = False

    if event.get("schema_version") != SCHEMA_VERSION:
        event["schema_version"] = SCHEMA_VERSION
        changed = True

    if "constraints_evaluated" not in event:
        event["constraints_evaluated"] = list(BASELINE_EVAL)
        changed = True
    else:
        # merge baseline + existing (e.g., raid0_policy)
        if isinstance(event.get("constraints_evaluated"), list):
            merged = list(dict.fromkeys(list(BASELINE_EVAL) + event["constraints_evaluated"]))
            if merged != event["constraints_evaluated"]:
                event["constraints_evaluated"] = merged
                changed = True

    if "constraints_evaluated" not in event:
        # v1 baseline: what we explicitly claim to check
        event["constraints_evaluated"] = ["human_override", "temporal_authority", "safety_limits"]
        changed = True
    if "constraint_evaluation_complete" not in event:
        event["constraint_evaluation_complete"] = True
        changed = True

    if "constraint_absence" not in event:
        # v1 default: empty list means "no absences explicitly logged"
        event["constraint_absence"] = []
        changed = True

    # v1 absence computation (mechanical)
    if isinstance(event.get("constraints_evaluated"), list):
        abs_set = set(event.get("constraint_absence") or [])
        ce = set(event["constraints_evaluated"])
        # human_override considered present only if explicit and not unknown
        if "human_override" in ce and event.get("human_override") in (None, "unknown"):
            abs_set.add("human_override")
        # temporal_authority is not per-event in v1; leave to status/verify layer
        # safety_limits present if constraints include any known guard keys
        c = event.get("constraints") or {}
        if "safety_limits" in ce and not any(k in c for k in ("safety_limits", "max_tokens", "max_duration")):
            abs_set.add("safety_limits")
        event["constraint_absence"] = sorted(abs_set)
        # if we have any absences, evaluation is incomplete only if we failed to check anything
        event["constraint_evaluation_complete"] = True

    # Ensure degradation_state exists and is coherent with event as written
    ds = derive_degradation_state(event)
    if event.get("degradation_state") != ds:
        event["degradation_state"] = ds
        changed = True

    return event, changed

def compute_chain(events: List[Tuple[Path, Dict[str, Any]]]) -> List[Tuple[Path, Dict[str, Any]]]:
    """
    Adds:
      - prev_hash: hash of previous event record (event_hash)
      - event_hash: SHA256(prev_hash || canonical_event_json_without_hash_fields)
    """
    prev = "0" * 64
    out = []
    for p, ev in events:
        # compute over a copy without hashes
        payload = dict(ev)
        payload.pop("event_hash", None)
        payload.pop("prev_hash", None)

        # include prev hash in the hashed payload deterministically
        # by hashing prev||canonical(payload)
        h = sha256_hex(bytes.fromhex(prev) + canonical_bytes(payload))

        # set fields
        if ev.get("prev_hash") != prev:
            ev["prev_hash"] = prev
        if ev.get("event_hash") != h:
            ev["event_hash"] = h

        prev = h
        out.append((p, ev))
    return out

def write_checkpoints(event_hashes: List[str], cadence: int = 10) -> List[Path]:
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    written = []

    for i in range(cadence, len(event_hashes) + 1, cadence):
        window = event_hashes[:i]
        root = merkle_root_hex(window)
        if root is None:
            continue

        # Use the i-th event as checkpoint id anchor if possible
        chk_id = f"events_{i:06d}"
        p = CHECKPOINTS / f"{chk_id}.json"

        chk = {
            "schema_version": SCHEMA_VERSION,
            "type": "merkle_checkpoint",
            "algorithm": HASH_ALGO,
            "event_count": i,
            "head_event_hash": window[-1],
            "merkle_root": root,
            "generated_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "cadence": cadence,
        }
        write_json(p, chk)
        written.append(p)

    # Always write "latest" checkpoint pointer
    latest_p = CHECKPOINTS / "latest.json"
    if event_hashes:
        # compute full root too
        full_root = merkle_root_hex(event_hashes)
        latest = {
            "schema_version": SCHEMA_VERSION,
            "type": "merkle_checkpoint_latest",
            "algorithm": HASH_ALGO,
            "event_count": len(event_hashes),
            "head_event_hash": event_hashes[-1],
            "merkle_root": full_root,
            "generated_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        }
        write_json(latest_p, latest)
        written.append(latest_p)

    return written

def main() -> int:
    files = list_event_files()
    if not files:
        print("no timestamp event files found in decisions/")
        return 1

    # Load + migrate fields
    loaded: List[Tuple[Path, Dict[str, Any]]] = []
    migrated = 0
    for p in files:
        ev = read_json(p)
        if not isinstance(ev, dict):
            print(f"skip unreadable: {p}")
            continue
        ev, changed = ensure_fields(ev)
        if changed:
            migrated += 1
        loaded.append((p, ev))

    # Chain
    chained = compute_chain(loaded)

    # Write back decisions
    for p, ev in chained:
        write_json(p, ev)

    # Collect hashes and checkpoint
    hashes = [ev["event_hash"] for _, ev in chained if isinstance(ev.get("event_hash"), str)]
    written = write_checkpoints(hashes, cadence=10)

    print(f"events: {len(chained)}")
    print(f"migrated_fields: {migrated}")
    print(f"head_event_hash: {hashes[-1] if hashes else None}")
    print(f"checkpoints_written: {len(written)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
