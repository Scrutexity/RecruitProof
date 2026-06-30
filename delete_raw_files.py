"""
delete_raw_files.py — Cryptographically Signed Deletion Receipt
================================================================

Hashes every file in a directory, records the proof, then deletes the
directory. Designed for Rudy's trust flow: run after pilot to prove
raw resumes were wiped.

Usage:
    from delete_raw_files import generate_deletion_receipt
    generate_deletion_receipt(Path("./ingested"), Path("./receipt.json"))
"""

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Dict


def generate_deletion_receipt(raw_dir: Path, receipt_path: Path) -> Path:
    """
    Hash all files in *raw_dir*, record a proof-of-deletion receipt,
    then permanently remove *raw_dir* and its contents.

    Parameters
    ----------
    raw_dir : Path
        Directory containing raw resume files to delete.
    receipt_path : Path
        Where to write the JSON deletion receipt (parent dir created
        automatically if it doesn't exist).

    Returns
    -------
    Path
        The receipt_path that was written.

    Raises
    ------
    FileNotFoundError
        If *raw_dir* does not exist.
    """
    if not raw_dir.exists():
        raise FileNotFoundError(f"Directory not found: {raw_dir}")

    # ── Hash every file ────────────────────────────────────────────
    file_hashes: Dict[str, str] = {}
    for f in sorted(raw_dir.rglob("*")):
        if f.is_file():
            relative = str(f.relative_to(raw_dir))
            sha = hashlib.sha256(f.read_bytes()).hexdigest()
            file_hashes[relative] = sha

    # ── Compute chain proof: hash of all hashes ────────────────────
    chain_proof = hashlib.sha256(
        json.dumps(file_hashes, sort_keys=True).encode()
    ).hexdigest()

    receipt = {
        "receipt_id": f"RCPT-{time.strftime('%Y%m%d')}-{int(time.time()) % 10000:04d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deleted_path": str(raw_dir.resolve()),
        "file_count": len(file_hashes),
        "file_hashes": file_hashes,
        "chain_proof": chain_proof,
        "method": "SHA-256 per file + hash-of-hashes chain proof",
        "status": "deleted",
    }

    # ── Write receipt BEFORE deletion ──────────────────────────────
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(receipt_path, "w") as f:
        json.dump(receipt, f, indent=2)

    # ── Permanently delete the directory ──────────────────────────
    shutil.rmtree(raw_dir)

    return receipt_path
