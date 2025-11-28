import os
import sys
import time
from pathlib import Path

from tinyorch.core import (
    run,
    run_parallel,
    keep_awake,
    prompt_enter,
    burn_iso,
    docker,
    ensure_dir,
    wait_for_files,
    spawn,
)

args = sys.argv[1:]
if not args:
    print("usage: zetronix-lark-zshades-2k.py TARGET | zetronix-lark-zshades-2k.py -r TIMESTAMP", file=sys.stderr)
    sys.exit(1)

if args[0] == "-r":
    if len(args) < 2:
        print("resume mode requires TIMESTAMP", file=sys.stderr)
        sys.exit(1)
    mode = "resume"
    target = args[1]
else:
    mode = "start"
    target = args[0]

job = os.environ["JOB"]
archive_root = Path(os.environ["ARCHIVE_ROOT"]).expanduser()
tz = os.environ["TZ"]
source_env = os.environ["SOURCE"]
upload_env = os.environ["UPLOAD"]

ts = target if mode == "resume" else time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

run_dir = ensure_dir(archive_root / job, ts)
iso_dir = ensure_dir(run_dir, "make_iso")
iso_path = iso_dir / f"{ts}.iso"

if mode == "start":
    source_dir = Path(target) / "DCIM" / "Movie"
else:
    source_dir = run_dir / "copy_to_stage"


prompt_enter(f"Press ENTER to {mode} {job} ({target})... ")
os.environ["RUN_DIR"] = str(run_dir)
keep_awake()


def copy_to_stage():
    out_dir = ensure_dir(run_dir, "copy_to_stage")
    script = 'umask 077; printf "%s\n" "$SOURCE" > /tmp/rclone.conf; rclone --config /tmp/rclone.conf move remote:/in /out --exclude "/.*" --exclude "**/.*" --delete-empty-src-dirs --progress'
    docker(
        "rclone/rclone:latest",
        "-lc",
        script,
        env={"TZ": tz, "SOURCE": source_env},
        volumes=[(source_dir, "/in"), (out_dir, "/out")],
        entrypoint="/bin/sh",
    )


def crunch_media():
    in_dir = run_dir / "copy_to_stage"
    out_dir = ensure_dir(run_dir, "crunch_media")
    docker(
        "ghcr.io/nashspence/vcrunch:next",
        "--verbose",
        "--svt-lp",
        "6",
        env={"TZ": tz},
        volumes=[(in_dir, "/in"), (out_dir, "/out")],
    )


def make_iso():
    in_dir = run_dir / "crunch_media"
    docker(
        "ghcr.io/nashspence/mkiso:next",
        "--out-file",
        iso_path.name,
        env={"TZ": tz},
        volumes=[(in_dir, "/in"), (iso_dir, "/out")],
    )


def cut_quick():
    in_dir = run_dir / "copy_to_stage"
    out_dir = ensure_dir(run_dir, "cut_quick")
    docker(
        "ghcr.io/nashspence/qcut:next",
        "--tp",
        "-24",
        "--svt-lp",
        "6",
        env={"TZ": tz},
        volumes=[(in_dir, "/in"), (out_dir, "/out")],
    )


def sync_to_share():
    data_dir = run_dir / "cut_quick"
    script = 'umask 077; printf "%s\n" "$UPLOAD" > /tmp/rclone.conf; rclone --config /tmp/rclone.conf copy /data remote: --exclude "/.*" --exclude "**/.*" --progress'
    docker(
        "rclone/rclone:latest",
        "-lc",
        script,
        env={"TZ": tz, "UPLOAD": upload_env},
        volumes=[(data_dir, "/data")],
        entrypoint="/bin/sh",
    )


def wait_and_burn():
    mark = run_dir / ".make_iso.done"
    wait_for_files([mark, iso_path])
    run(
        "burn_iso",
        lambda: burn_iso(str(iso_path)),
        retries=None,
        success_msg="Burn complete",
    )


burn_thread = spawn(wait_and_burn)

if mode == "start":
    run("copy_to_stage", copy_to_stage, success_msg="Files imported; you can disconnect the device.")

run("crunch_media", crunch_media)

run_parallel(
    [
        lambda: run("make_iso", make_iso),
        lambda: run("cut_quick", cut_quick),
    ]
)

run("sync_to_share", sync_to_share, success_msg="New cut available on the server.")

burn_thread.join()
