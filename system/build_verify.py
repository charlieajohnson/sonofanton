#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions"
CHECKPOINTS = ROOT / "checkpoints"
WITNESS = ROOT / "witness"
PUBLIC_WITNESS = ROOT / "public" / "witness"

SIG_JSON = CHECKPOINTS / "latest.sig"
CHECKPOINT_JSON = CHECKPOINTS / "latest.json"
SIG_TMP = CHECKPOINTS / ".latest.sig.ssh"

ALLOWED = ROOT / "witness" / "keys" / "allowed_signers"
PRINCIPAL = "sonofanton_checkpoint_ed25519"
NAMESPACE = "sonofanton-checkpoint"

SCHEMA_VERSION = "1.0.0"
TS_RE = re.compile(r"^\d{8}T\d{6}Z$")

def read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def list_event_files() -> List[Path]:
    files = []
    for p in DECISIONS.glob("*.json"):
        if TS_RE.match(p.stem):
            files.append(p)
    return sorted(files, key=lambda x: x.stem)

def verify_chain(events: List[Dict[str, Any]]) -> bool:
    prev = "0" * 64
    for ev in events:
        if ev.get("prev_hash") != prev:
            return False
        payload = dict(ev)
        payload.pop("event_hash", None)
        payload.pop("prev_hash", None)
        # chain hash = sha256(prev_bytes || canonical(payload))
        h = sha256_hex(bytes.fromhex(prev) + canonical_bytes(payload))
        if ev.get("event_hash") != h:
            return False
        prev = h
    return True

def verify_checkpoint_signature() -> bool:
    sig_obj = read_json(SIG_JSON)
    if not sig_obj or not SIG_JSON.exists() or not CHECKPOINT_JSON.exists() or not ALLOWED.exists():
        return False
    sig_raw = base64.b64decode(sig_obj["signature"])
    SIG_TMP.write_bytes(sig_raw)
    payload = canonical_bytes(read_json(CHECKPOINT_JSON) or {})
    p = subprocess.run(
        ["ssh-keygen", "-Y", "verify", "-f", str(ALLOWED), "-I", PRINCIPAL, "-n", NAMESPACE, "-s", str(SIG_TMP)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        SIG_TMP.unlink()
    except FileNotFoundError:
        pass
    return p.returncode == 0

def main() -> int:
    checkpoint = read_json(CHECKPOINT_JSON) or {}
    sig_ok = verify_checkpoint_signature()

    files = list_event_files()
    events = []
    for f in files:
        ev = read_json(f)
        if isinstance(ev, dict):
            events.append(ev)

    chain_ok = verify_chain(events)

    head = checkpoint.get("head_event_hash")
    count = checkpoint.get("event_count")

    out = {
        "schema_version": SCHEMA_VERSION,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verification_scope": "full_history",
        "chain": {
            "event_count": count if isinstance(count, int) else len(events),
            "head_event_hash": head,
            "hash_chain_valid": bool(chain_ok),
        },
        "checkpoint": {
            "merkle_root": checkpoint.get("merkle_root"),
            "event_count": checkpoint.get("event_count"),
            "head_event_hash": checkpoint.get("head_event_hash"),
            "generated_at": checkpoint.get("generated_at"),
            "signature_valid": bool(sig_ok),
            "signing_key_id": PRINCIPAL,
        },
    }

    WITNESS.mkdir(parents=True, exist_ok=True)
    PUBLIC_WITNESS.mkdir(parents=True, exist_ok=True)

    (WITNESS / "verify.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (PUBLIC_WITNESS / "verify.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print("wrote witness/verify.json and public/witness/verify.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
