#!/usr/bin/env python3
import os, sys
from pathlib import Path
from datetime import datetime
from tinyorch.core import dr, make_notifier, run_stage, run_parallel, rclone_sync

JOB_CONTEXT = os.getenv("JOB_CONTEXT", "zetronix-lark-zshades-2k")
ARCHIVE_ROOT = Path(os.getenv("ARCHIVE_ROOT", str(Path.home() / "archive")))

source_dir = Path(sys.argv[1]) / "DCIM" / "Movie"

input(f"Press Enter to archive {JOB_CONTEXT}: ")
now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

run_dir = ARCHIVE_ROOT / JOB_CONTEXT / now
stage_dir, crunch_dir, iso_dir, cut_dir = (
    run_dir / "copy_to_stage",
    run_dir / "crunch_media",
    run_dir / "make_iso",
    run_dir / "cut_quick",
)
for d in (stage_dir, crunch_dir, iso_dir, cut_dir): d.mkdir(parents=True, exist_ok=True)

marks = {
    "copy_to_stage": run_dir / ".copy_to_stage.done",
    "crunch_media": run_dir / ".crunch_media.done",
    "make_iso": run_dir / ".make_iso.done",
    "cut_quick": run_dir / ".cut_quick.done",
    "sync_to_share": run_dir / ".sync_to_share.done",
}

iso_name = f"{now}.iso"
iso_path = iso_dir / iso_name

run_stage(
    marks["copy_to_stage"], "copy_to_stage", 
    lambda: dr(
        "-v", f"{source_dir}:/in:ro",
        "-v", f"{stage_dir}:/out",
        "instrumentisto/rsync-ssh:latest", "sh", "-lc",
        "rsync -a --partial --info=progress2 "
        "--exclude '/.*' --exclude '**/.*' "
        "--remove-source-files /in/ /out/ && "
        "find /in -depth -type d -empty -delete"
    ),
    "Files imported; you can disconnect the device."
)

run_stage(
    marks["crunch_media"], "crunch_media",
    lambda: dr(
        "-v", f"{stage_dir}:/in",
        "-v", f"{crunch_dir}:/out",
        "ghcr.io/nashspence/vcrunch:next",
        "--verbose", "--svt-lp", "6"
    )
)

run_parallel([
    lambda: run_stage(
        marks["make_iso"], "make_iso",
        lambda: dr(
            "-v", f"{crunch_dir}:/in",
            "-v", f"{iso_dir}:/out",
            "ghcr.io/nashspence/mkiso:next",
            "--out-file", iso_name
        )
    ) if not marks["make_iso"].exists() else None,
    lambda: run_stage(
        marks["cut_quick"], "cut_quick",
        lambda: dr(
            "-v", f"{stage_dir}:/in",
            "-v", f"{cut_dir}:/out",
            "ghcr.io/nashspence/mkiso:qcut",
            "--tp", "-24", "--svt-lp", "6"
        )
    ) if not marks["cut_quick"].exists() else None,
])

run_stage(
    marks["sync_to_share"], "sync_to_share",
    lambda: rclone_sync(cut_dir),
    "New cut available on the server."
)

print(str(iso_path))
