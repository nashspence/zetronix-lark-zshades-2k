#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from datetime import UTC, datetime
from tinyorch.core import run, run_parallel

JOB = os.environ["JOB"]
MODE = os.environ.get("MODE", "start").lower()
TARGET = os.environ.get("TARGET")

if not TARGET:
    print("TARGET is required", file=sys.stderr)
    sys.exit(1)

ARCHIVE_ROOT = Path(os.environ["OUT"]).expanduser()

if MODE == "start":
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
elif MODE == "resume":
    timestamp = TARGET
else:
    print(f"Unsupported MODE: {MODE}", file=sys.stderr)
    sys.exit(1)

run_dir = ARCHIVE_ROOT / JOB / timestamp
run_dir.mkdir(parents=True, exist_ok=True)

os.environ["JOB_CONTEXT"] = JOB
os.environ["RUN_DIR"] = str(run_dir)

if MODE == "start":
    source_dir = Path(TARGET) / "DCIM" / "Movie"
else:
    source_dir = run_dir / "copy_to_stage"

os.environ["SOURCE_DIR"] = str(source_dir)

iso_name = f"{timestamp}.iso"
iso_path = run_dir / "make_iso" / iso_name
os.environ["ISO_NAME"] = iso_name

if MODE == "start":
    run(
        "copy_to_stage",
        success_msg="Files imported; you can disconnect the device.",
    )

run("crunch_media")

run_parallel([
    lambda: run("make_iso"),
    lambda: run("cut_quick"),
])

run(
    "sync_to_share",
    success_msg="New cut available on the server.",
)

print(str(iso_path))
