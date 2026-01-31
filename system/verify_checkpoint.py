#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "checkpoints" / "latest.json"
SIG = ROOT / "checkpoints" / "latest.sig"
PUB = ROOT / "witness" / "keys" / "sonofanton_checkpoint_ed25519.pub"

def canonical_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

def main() -> int:
    sig_obj = json.loads(SIG.read_text(encoding="utf-8"))
    payload = canonical_bytes(json.loads(CHECKPOINT.read_text(encoding="utf-8")))
    sig_raw = base64.b64decode(sig_obj["signature"])

    p = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(PUB),
            "-n",
            "sonofanton-checkpoint",
            "-s",
            "/dev/stdin",
        ],
        input=sig_raw + payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if p.returncode == 0:
        print("checkpoint signature VALID")
        return 0
    else:
        print("checkpoint signature INVALID")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
