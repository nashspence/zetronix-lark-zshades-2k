import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from tinyorch.core import burn_iso, prompt_enter, run

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

run_dir = archive_root / job / ts
run_dir.mkdir(parents=True, exist_ok=True)
iso_dir = run_dir / "make_iso"
iso_dir.mkdir(parents=True, exist_ok=True)
iso_path = iso_dir / f"{ts}.iso"

if mode == "start":
    source_dir = Path(target) / "DCIM" / "Movie"
else:
    source_dir = run_dir / "copy_to_stage"


prompt_enter(f"Press ENTER to {mode} {job} ({target})... ")
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
