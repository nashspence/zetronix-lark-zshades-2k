import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from tinyorch.core import burn_iso, run

required = ["JOB", "ARCHIVE_ROOT", "TZ", "SOURCE", "UPLOAD", "RUN_MODE", "RUN_TS"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print("missing required env: " + ", ".join(missing), file=sys.stderr)
    sys.exit(2)

mode = os.environ["RUN_MODE"]
ts = os.environ["RUN_TS"]

if mode not in ("start", "resume"):
    print(f"invalid RUN_MODE: {mode!r} (expected 'start' or 'resume')", file=sys.stderr)
    sys.exit(2)

if mode == "start" and not os.environ.get("RUN_TARGET"):
    print("missing required env: RUN_TARGET (required when RUN_MODE=start)", file=sys.stderr)
    sys.exit(2)

job = os.environ["JOB"]
archive_root = Path(os.environ["ARCHIVE_ROOT"]).expanduser()
tz = os.environ["TZ"]
source_env = os.environ["SOURCE"]
upload_env = os.environ["UPLOAD"]

run_dir = archive_root / job / ts
run_dir.mkdir(parents=True, exist_ok=True)

iso_dir = run_dir / "make_iso"
iso_dir.mkdir(parents=True, exist_ok=True)

iso_path = iso_dir / f"{ts}.iso"

if mode == "start":
    source_dir = Path(os.environ["RUN_TARGET"]) / "DCIM" / "Movie"
else:
    source_dir = run_dir / "copy_to_stage"

os.environ["RUN_DIR"] = str(run_dir)


def copy_to_stage():
    out_dir = run_dir / "copy_to_stage"
    out_dir.mkdir(parents=True, exist_ok=True)
    script = 'umask 077; printf "%s\\n" "$SOURCE" > /tmp/rclone.conf; rclone --config /tmp/rclone.conf move remote:/in /out --exclude "/.*" --exclude "**/.*" --delete-empty-src-dirs --progress'
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"TZ={tz}",
            "-e",
            f"SOURCE={source_env}",
            "-v",
            f"{source_dir}:/in",
            "-v",
            f"{out_dir}:/out",
            "--entrypoint",
            "/bin/sh",
            "rclone/rclone:latest",
            "-lc",
            script,
        ],
        check=True,
    )


def crunch_media():
    in_dir = run_dir / "copy_to_stage"
    out_dir = run_dir / "crunch_media"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"TZ={tz}",
            "-v",
            f"{in_dir}:/in",
            "-v",
            f"{out_dir}:/out",
            "ghcr.io/nashspence/vcrunch:next",
            "--verbose",
            "--svt-lp",
            "6",
        ],
        check=True,
    )


def make_iso():
    in_dir = run_dir / "crunch_media"
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"TZ={tz}",
            "-v",
            f"{in_dir}:/in",
            "-v",
            f"{iso_dir}:/out",
            "ghcr.io/nashspence/mkiso:next",
            "--out-file",
            iso_path.name,
        ],
        check=True,
    )


def cut_quick():
    in_dir = run_dir / "copy_to_stage"
    out_dir = run_dir / "cut_quick"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"TZ={tz}",
            "-v",
            f"{in_dir}:/in",
            "-v",
            f"{out_dir}:/out",
            "ghcr.io/nashspence/qcut:next",
            "--tp",
            "-24",
            "--svt-lp",
            "6",
        ],
        check=True,
    )


def sync_to_share():
    data_dir = run_dir / "cut_quick"
    script = 'umask 077; printf "%s\\n" "$UPLOAD" > /tmp/rclone.conf; rclone --config /tmp/rclone.conf copy /data remote: --exclude "/.*" --exclude "**/.*" --progress'
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"TZ={tz}",
            "-e",
            f"UPLOAD={upload_env}",
            "-v",
            f"{data_dir}:/data",
            "--entrypoint",
            "/bin/sh",
            "rclone/rclone:latest",
            "-lc",
            script,
        ],
        check=True,
    )


def wait_and_burn():
    mark = run_dir / ".make_iso.done"
    while not mark.exists() or not iso_path.exists():
        time.sleep(5)
    run(
        "burn_iso",
        lambda: burn_iso(str(iso_path)),
        retries=None,
        success_msg="Burn complete",
    )


burn_thread = threading.Thread(target=wait_and_burn, daemon=True)
burn_thread.start()

if mode == "start":
    run("copy_to_stage", copy_to_stage, success_msg="Files imported; you can disconnect the device.")

run("crunch_media", crunch_media)

threads = [
    threading.Thread(target=lambda: run("make_iso", make_iso)),
    threading.Thread(target=lambda: run("cut_quick", cut_quick)),
]
for t in threads:
    t.start()
for t in threads:
    t.join()

run("sync_to_share", sync_to_share, success_msg="New cut available on the server.")

burn_thread.join()