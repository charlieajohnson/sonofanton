#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "checkpoints" / "latest.json"
SIG_JSON = ROOT / "checkpoints" / "latest.sig"
SIG_TMP = ROOT / "checkpoints" / ".latest.sig.ssh"

ALLOWED = ROOT / "witness" / "keys" / "allowed_signers"
PRINCIPAL = "sonofanton_checkpoint_ed25519"
NAMESPACE = "sonofanton-checkpoint"

def canonical_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

def main() -> int:
    if not CHECKPOINT.exists():
        print("missing checkpoints/latest.json")
        return 2
    if not SIG_JSON.exists():
        print("missing checkpoints/latest.sig")
        return 2
    if not ALLOWED.exists():
        print("missing witness/keys/allowed_signers")
        return 2

    sig_obj = json.loads(SIG_JSON.read_text(encoding="utf-8"))
    sig_raw = base64.b64decode(sig_obj["signature"])
    SIG_TMP.write_bytes(sig_raw)

    payload = canonical_bytes(json.loads(CHECKPOINT.read_text(encoding="utf-8")))

    p = subprocess.run(
        [
            "ssh-keygen",
            "-Y", "verify",
            "-f", str(ALLOWED),
            "-I", PRINCIPAL,
            "-n", NAMESPACE,
            "-s", str(SIG_TMP),
        ],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        SIG_TMP.unlink()
    except FileNotFoundError:
        pass

    if p.returncode == 0:
        print("checkpoint signature VALID")
        return 0
    else:
        print("checkpoint signature INVALID")
        if p.stderr:
            print(p.stderr.decode("utf-8", errors="replace").strip())
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
