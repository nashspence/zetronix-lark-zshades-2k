#!/usr/bin/env python3
import os, sys
from pathlib import Path
from datetime import datetime
from tinyorch.core import dr, run_stage, run_parallel, rclone_sync, rsync_import

JOB_CONTEXT = os.getenv("JOB_CONTEXT", "zetronix-lark-zshades-2k")
ARCHIVE_ROOT = Path(os.getenv("ARCHIVE_ROOT", str(Path.home() / "archive")))

source_dir = Path(sys.argv[1]) / "DCIM" / "Movie"

input(f"Press Enter to archive {JOB_CONTEXT}: ")
now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

run_dir = ARCHIVE_ROOT / JOB_CONTEXT / now
stage_dir = run_dir / "copy_to_stage"
crunch_dir = run_dir / "crunch_media"
iso_dir = run_dir / "make_iso"
cut_dir = run_dir / "cut_quick"

for d in (stage_dir, crunch_dir, iso_dir, cut_dir):
    d.mkdir(parents=True, exist_ok=True)

os.environ["RUN_DIR"] = str(run_dir)

iso_name = f"{now}.iso"
iso_path = iso_dir / iso_name

run_stage(
    "copy_to_stage",
    lambda: rsync_import(source_dir, stage_dir),
    success_msg="Files imported; you can disconnect the device."
)

run_stage(
    "crunch_media",
    lambda: dr(
        "-v", f"{stage_dir}:/in",
        "-v", f"{crunch_dir}:/out",
        "ghcr.io/nashspence/vcrunch:next",
        "--verbose", "--svt-lp", "6"
    )
)

run_parallel([
    lambda: run_stage(
        "make_iso",
        lambda: dr(
            "-v", f"{crunch_dir}:/in",
            "-v", f"{iso_dir}:/out",
            "ghcr.io/nashspence/mkiso:next",
            "--out-file", iso_name
        )
    ),
    lambda: run_stage(
        "cut_quick",
        lambda: dr(
            "-v", f"{stage_dir}:/in",
            "-v", f"{cut_dir}:/out",
            "ghcr.io/nashspence/mkiso:qcut",
            "--tp", "-24", "--svt-lp", "6"
        )
    ),
])

run_stage(
    "sync_to_share",
    lambda: rclone_sync(cut_dir),
    success_msg="New cut available on the server."
)

print(str(iso_path))
