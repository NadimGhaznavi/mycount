#!/usr/bin/env python3
"""Verify pinned BMForge files locally without Git or network access."""

from hashlib import sha256
from pathlib import Path
import json
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    lock = json.loads((root / ".agents/bmforge/lock.json").read_text(encoding="utf-8"))
    if lock["schema"] != 1:
        raise ValueError("Unsupported BMForge lock schema")
    failed = False
    for name, installed in sorted(lock["skills"].items()):
        directory = root / ".agents/skills" / name
        digest = sha256()
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        if directory.is_symlink() or any(path.is_symlink() for path in directory.rglob("*")):
            print(f"INVALID {name}: symlinks are not permitted")
            failed = True
            continue
        for path in files:
            relative = path.relative_to(directory).as_posix()
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(sha256(path.read_bytes()).digest())
        intact = directory.is_dir() and digest.hexdigest() == installed["sha256"]
        print(f"{'OK' if intact else 'MODIFIED OR MISSING'} {name} ({installed['spec_version']})")
        failed |= not intact
    manager = root / ".agents/bmforge/manage.py"
    intact = manager.is_file() and not manager.is_symlink() and sha256(manager.read_bytes()).hexdigest() == lock["manager_sha256"]
    print(f"{'OK' if intact else 'MODIFIED OR MISSING'} BMForge manager")
    failed |= not intact
    print("Integrity only; upstream updates were not checked. No files were changed.")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
