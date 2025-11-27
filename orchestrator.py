#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from tinyorch.core import run, run_parallel

JOB = os.environ["JOB"]
MODE = os.environ.get("MODE", "start").lower()
TARGET = os.environ.get("TARGET")

if not TARGET:
    print("TARGET is required", file=sys.stderr)
    sys.exit(1)

run_dir = Path(os.environ["RUN_DIR"]).expanduser()
run_dir.mkdir(parents=True, exist_ok=True)

os.environ["RUN_DIR"] = str(run_dir)

if MODE == "start":
    source_dir = Path(TARGET) / "DCIM" / "Movie"
elif MODE == "resume":
    source_dir = run_dir / "copy_to_stage"
else:
    print(f"Unsupported MODE: {MODE}", file=sys.stderr)
    sys.exit(1)

os.environ["SOURCE_DIR"] = str(source_dir)

iso_path = Path(os.environ["ISO_PATH"])
iso_dir = iso_path.parent
iso_name = iso_path.name

os.environ["ISO_PATH"] = str(iso_path)
os.environ["ISO_DIR"] = str(iso_dir)
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

sys.exit(0)