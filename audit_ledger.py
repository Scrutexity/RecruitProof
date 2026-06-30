"""
audit_ledger.py — Hash-Chained Audit Ledger
============================================

A tamper-evident audit log where each event includes the SHA-256 hash of the
previous event. Any modification to a past event breaks the chain, making
tampering detectable.

Usage:
    from audit_ledger import AuditLedger

    ledger = AuditLedger("runs/pilot_001/audit_ledger.jsonl")
    ledger.append("ingest_started", {"zip": "export.zip", "file_count": 5000})
    ledger.append("ingest_complete", {"parsed": 4987, "failed": 13})
    ledger.verify()  # returns True if chain is intact

CLI:
    python audit_ledger.py --verify runs/pilot_001/audit_ledger.jsonl
    python audit_ledger.py --read runs/pilot_001/audit_ledger.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLedger:
    """A hash-chained, tamper-evident audit log."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._previous_hash = "0" * 64  # genesis hash
        # Load existing chain if the file exists
        if self.path.exists():
            self._load_chain()

    def _load_chain(self) -> None:
        """Load the existing chain and set _previous_hash to the last event's hash."""
        last_hash = "0" * 64
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    last_hash = event.get("event_hash", last_hash)
                except json.JSONDecodeError:
                    continue
        self._previous_hash = last_hash

    def append(self, action: str, details: Dict[str, Any], actor: str = "system",
               run_id: str = "", pii_hashes: Optional[List[str]] = None) -> Dict:
        """Append a new event to the ledger. Returns the event dict."""
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "actor": actor,
            "action": action,
            "details": details,
            "previous_hash": self._previous_hash,
        }
        if pii_hashes:
            event["pii_hashes"] = pii_hashes

        # Compute this event's hash
        event_str = json.dumps(event, sort_keys=True)
        event["event_hash"] = hashlib.sha256(event_str.encode()).hexdigest()

        # Append to file
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")

        # Update chain pointer
        self._previous_hash = event["event_hash"]
        return event

    def verify(self) -> bool:
        """Verify the hash chain is intact. Returns True if no tampering detected."""
        if not self.path.exists():
            return True  # empty ledger is valid

        previous_hash = "0" * 64
        line_num = 0
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                line_num += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ✗ Line {line_num}: invalid JSON: {e}", file=sys.stderr)
                    return False

                stored_hash = event.pop("event_hash", None)
                if not stored_hash:
                    print(f"  ✗ Line {line_num}: missing event_hash", file=sys.stderr)
                    return False

                # Check previous_hash linkage
                if event.get("previous_hash", "") != previous_hash:
                    print(f"  ✗ Line {line_num}: previous_hash mismatch "
                          f"(expected {previous_hash[:12]}..., got {event.get('previous_hash', '')[:12]}...)",
                          file=sys.stderr)
                    return False

                # Recompute hash
                event_str = json.dumps(event, sort_keys=True)
                computed_hash = hashlib.sha256(event_str.encode()).hexdigest()
                if computed_hash != stored_hash:
                    print(f"  ✗ Line {line_num}: event_hash mismatch "
                          f"(stored {stored_hash[:12]}..., computed {computed_hash[:12]}...)",
                          file=sys.stderr)
                    return False

                previous_hash = stored_hash

        print(f"  ✓ Chain intact ({line_num} events verified)", file=sys.stderr)
        return True

    def read_all(self) -> List[Dict]:
        """Read all events from the ledger."""
        events = []
        if not self.path.exists():
            return events
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — hash-chained audit ledger")
    ap.add_argument("path", help="Path to the audit_ledger.jsonl file")
    ap.add_argument("--verify", action="store_true", help="Verify the hash chain")
    ap.add_argument("--read", action="store_true", help="Print all events")
    args = ap.parse_args()

    ledger = AuditLedger(args.path)

    if args.verify:
        ok = ledger.verify()
        sys.exit(0 if ok else 1)
    elif args.read:
        events = ledger.read_all()
        for e in events:
            print(json.dumps(e, indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
