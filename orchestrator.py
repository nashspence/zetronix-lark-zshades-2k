#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from datetime import datetime
from tinyorch.core import run, run_parallel


JOB_CONTEXT = os.getenv("JOB_CONTEXT", "zetronix-lark-zshades-2k")
ARCHIVE_ROOT = Path(os.getenv("ARCHIVE_ROOT", str(Path.home() / "archive")))

source_dir = Path(sys.argv[1]) / "DCIM" / "Movie"

input(f"Press Enter to archive {JOB_CONTEXT}: ")
now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

run_dir = ARCHIVE_ROOT / JOB_CONTEXT / now

os.environ["JOB_CONTEXT"] = JOB_CONTEXT
os.environ["RUN_DIR"] = str(run_dir)
os.environ["SOURCE_DIR"] = str(source_dir)

iso_name = f"{now}.iso"
iso_path = run_dir / "make_iso" / iso_name
os.environ["ISO_NAME"] = iso_name

run(
    "copy_to_stage",
    success_msg="Files imported; you can disconnect the device."
)

run("crunch_media")

run_parallel([
    lambda: run("make_iso"),
    lambda: run("cut_quick"),
])

run(
    "sync_to_share",
    success_msg="New cut available on the server."
)

print(str(iso_path))
