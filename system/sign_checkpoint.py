#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "checkpoints" / "latest.json"
SIG = ROOT / "checkpoints" / "latest.sig"
KEY = ROOT / "witness" / "keys" / "sonofanton_checkpoint_ed25519"

def canonical_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

def main() -> int:
    if not CHECKPOINT.exists():
        raise SystemExit("missing checkpoints/latest.json")

    obj = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    payload = canonical_bytes(obj)

    # Sign using ssh-keygen (Ed25519)
    p = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(KEY), "-n", "sonofanton-checkpoint"],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    # Extract the raw signature block
    sig_b64 = base64.b64encode(p.stdout).decode("ascii")

    SIG.write_text(
        json.dumps(
            {
                "algorithm": "ed25519",
                "key_id": "sonofanton_checkpoint_ed25519",
                "signed_file": "checkpoints/latest.json",
                "signature": sig_b64,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("signed checkpoints/latest.json → checkpoints/latest.sig")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
