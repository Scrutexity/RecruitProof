"""
backup.py — RecruitProof Encrypted Backup & Restore
==================================================

Creates timestamped, optionally-encrypted tarball backups of the /data
directory. Supports restore, retention pruning, and optional S3 upload.

Usage:
    # Create an encrypted backup
    python backup.py --output /data/backups/ --encrypt

    # Restore from a specific backup
    python backup.py --restore /data/backups/recruitproof_2026-07-15_020000.tar.gz

    # Restore the latest backup
    python backup.py --restore latest --output /data/backups/

    # Prune backups older than 30 days
    python backup.py --prune --retention-days 30 --output /data/backups/

Environment variables:
    BACKUP_ENCRYPTION_KEY   — Fernet key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    AWS_S3_BUCKET           — Optional S3 upload destination
    AWS_S3_PREFIX           — S3 key prefix (default: recruitproof-backups)
    AWS_ACCESS_KEY_ID       — S3 credentials
    AWS_SECRET_ACCESS_KEY   — S3 credentials
    AWS_REGION              — S3 region (default: us-east-1)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet():
    """Return a Fernet instance if BACKUP_ENCRYPTION_KEY is set, else None."""
    key = os.environ.get("BACKUP_ENCRYPTION_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception as e:
        print(f"[backup] WARN: BACKUP_ENCRYPTION_KEY is set but invalid: {e}", file=sys.stderr)
        return None


def _encrypt_file(in_path: str, out_path: str, fernet) -> None:
    """Encrypt a file with Fernet (AES-128-CBC + HMAC-SHA256)."""
    with open(in_path, "rb") as f:
        data = f.read()
    token = fernet.encrypt(data)
    with open(out_path, "wb") as f:
        f.write(token)


def _decrypt_file(in_path: str, out_path: str, fernet) -> None:
    """Decrypt a file. Raises if the key is wrong."""
    with open(in_path, "rb") as f:
        token = f.read()
    data = fernet.decrypt(token)
    with open(out_path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def create_backup(data_dir: str, output_dir: str, encrypt: bool = True,
                  upload_s3: bool = False) -> str:
    """Create a timestamped backup. Returns the path to the backup file."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"[backup] ERROR: data dir {data_dir} does not exist", file=sys.stderr)
        sys.exit(2)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.gmtime())
    backup_name = f"recruitproof_{timestamp}"
    tarball_path = out_path / f"{backup_name}.tar.gz"
    encrypted_path = out_path / f"{backup_name}.tar.gz.enc"

    # Exclude the backups dir itself from the tarball (avoid recursion)
    print(f"[backup] creating tarball of {data_dir} → {tarball_path}", file=sys.stderr)
    t0 = time.time()
    cmd = ["tar", "-czf", str(tarball_path),
           "--exclude", str(out_path.resolve()),
           "-C", str(data_path.parent),
           data_path.name]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[backup] tar failed: {result.stderr}", file=sys.stderr)
        sys.exit(3)
    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    print(f"[backup] tarball created ({size_mb:.1f} MB in {time.time()-t0:.1f}s)", file=sys.stderr)

    final_path = str(tarball_path)

    # Encrypt
    if encrypt:
        fernet = _get_fernet()
        if fernet is None:
            print("[backup] WARN: --encrypt requested but BACKUP_ENCRYPTION_KEY not set. "
                  "Saving unencrypted backup.", file=sys.stderr)
        else:
            print(f"[backup] encrypting → {encrypted_path}", file=sys.stderr)
            _encrypt_file(str(tarball_path), str(encrypted_path), fernet)
            tarball_path.unlink()  # remove the unencrypted tarball
            final_path = str(encrypted_path)
            print(f"[backup] encrypted backup saved ({encrypted_path.stat().st_size / (1024*1024):.1f} MB)", file=sys.stderr)

    # Optional S3 upload
    if upload_s3:
        _upload_to_s3(final_path)

    # Write a manifest
    manifest_path = out_path / f"{backup_name}.manifest.json"
    import json
    with open(manifest_path, "w") as f:
        json.dump({
            "backup_file": os.path.basename(final_path),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "size_bytes": os.path.getsize(final_path),
            "encrypted": encrypt and _get_fernet() is not None,
            "uploaded_to_s3": upload_s3,
            "data_dir": data_dir,
        }, f, indent=2)

    print(f"\n[backup] DONE → {final_path}", file=sys.stderr)
    return final_path


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_backup(backup_path: str, data_dir: str, output_dir: Optional[str] = None) -> None:
    """Restore from a backup. If backup_path == 'latest', find the newest in output_dir."""
    if backup_path == "latest":
        if not output_dir:
            print("[backup] ERROR: --output required when --restore latest", file=sys.stderr)
            sys.exit(2)
        backups = sorted(Path(output_dir).glob("recruitproof_*.tar.gz*"))
        if not backups:
            print(f"[backup] ERROR: no backups found in {output_dir}", file=sys.stderr)
            sys.exit(2)
        backup_path = str(backups[-1])
        print(f"[backup] using latest: {backup_path}", file=sys.stderr)

    bp = Path(backup_path)
    if not bp.exists():
        print(f"[backup] ERROR: backup file not found: {backup_path}", file=sys.stderr)
        sys.exit(2)

    data_path = Path(data_dir)

    # Decrypt if needed
    is_encrypted = bp.suffix == ".enc"
    tarball_to_extract = bp
    tmp_decrypted = None
    if is_encrypted:
        fernet = _get_fernet()
        if fernet is None:
            print("[backup] ERROR: backup is encrypted but BACKUP_ENCRYPTION_KEY not set", file=sys.stderr)
            sys.exit(2)
        tmp_decrypted = bp.with_suffix("")  # strip .enc
        print(f"[backup] decrypting → {tmp_decrypted}", file=sys.stderr)
        _decrypt_file(str(bp), str(tmp_decrypted), fernet)
        tarball_to_extract = tmp_decrypted

    # Move existing data dir aside (if any)
    if data_path.exists():
        backup_of_existing = data_path.with_name(f"{data_path.name}.pre_restore_{int(time.time())}")
        print(f"[backup] moving existing {data_dir} aside → {backup_of_existing}", file=sys.stderr)
        data_path.rename(backup_of_existing)

    # Extract
    print(f"[backup] extracting {tarball_to_extract} → {data_path.parent}/", file=sys.stderr)
    cmd = ["tar", "-xzf", str(tarball_to_extract), "-C", str(data_path.parent)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[backup] extraction failed: {result.stderr}", file=sys.stderr)
        sys.exit(3)
    print(f"[backup] restored to {data_dir}", file=sys.stderr)

    # Clean up tmp decrypted file
    if tmp_decrypted and tmp_decrypted.exists():
        tmp_decrypted.unlink()


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------

def prune_backups(output_dir: str, retention_days: int = 30) -> int:
    """Delete backups older than retention_days. Returns count deleted."""
    out_path = Path(output_dir)
    if not out_path.exists():
        return 0
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for p in out_path.glob("recruitproof_*.tar.gz*"):
        if p.stat().st_mtime < cutoff:
            p.unlink()
            deleted += 1
            print(f"[backup] pruned {p.name}", file=sys.stderr)
    # Also prune old manifests
    for p in out_path.glob("recruitproof_*.manifest.json"):
        if p.stat().st_mtime < cutoff:
            p.unlink()
    return deleted


# ---------------------------------------------------------------------------
# S3 upload (optional)
# ---------------------------------------------------------------------------

def _upload_to_s3(file_path: str) -> bool:
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        print("[backup] AWS_S3_BUCKET not set, skipping S3 upload", file=sys.stderr)
        return False
    try:
        import boto3
    except ImportError:
        print("[backup] boto3 not installed. Run: pip install boto3", file=sys.stderr)
        return False
    prefix = os.environ.get("AWS_S3_PREFIX", "recruitproof-backups")
    key = f"{prefix}/{os.path.basename(file_path)}"
    print(f"[backup] uploading to s3://{bucket}/{key}", file=sys.stderr)
    s3 = boto3.client("s3",
                      aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                      region_name=os.environ.get("AWS_REGION", "us-east-1"))
    s3.upload_file(file_path, bucket, key)
    print(f"[backup] uploaded", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="RecruitProof — encrypted backup & restore")
    ap.add_argument("--output", default="/data/backups/", help="Backup output directory")
    ap.add_argument("--data-dir", default=os.environ.get("RECRUITPROOF_DATA_DIR", "/data"), help="Data directory to back up")
    ap.add_argument("--encrypt", action="store_true", default=True, help="Encrypt with BACKUP_ENCRYPTION_KEY (default: on)")
    ap.add_argument("--no-encrypt", dest="encrypt", action="store_false", help="Don't encrypt")
    ap.add_argument("--upload-s3", action="store_true", help="Upload to S3 (requires boto3 + AWS creds)")
    ap.add_argument("--restore", metavar="BACKUP", default=None,
                    help="Restore from a backup file (or 'latest' to use the newest)")
    ap.add_argument("--prune", action="store_true", help="Delete backups older than --retention-days")
    ap.add_argument("--retention-days", type=int, default=30, help="Prune retention (default: 30)")
    args = ap.parse_args()

    if args.restore:
        restore_backup(args.restore, args.data_dir, output_dir=args.output)
    elif args.prune:
        n = prune_backups(args.output, args.retention_days)
        print(f"[backup] pruned {n} backups older than {args.retention_days} days", file=sys.stderr)
    else:
        create_backup(args.data_dir, args.output, encrypt=args.encrypt, upload_s3=args.upload_s3)
        # Always prune after a new backup
        prune_backups(args.output, args.retention_days)


if __name__ == "__main__":
    main()
