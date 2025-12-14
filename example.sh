#!/bin/sh

: "${XDG_CACHE_HOME:=$HOME/.cache}"
U=https://raw.githubusercontent.com/nashspence/tinyorch/main/install.sh
F="${TINYORCH_BOOT:-$XDG_CACHE_HOME/tinyorch/install.sh}"
[ -n "${TINYORCH_BOOT:-}" ] || { mkdir -p "$(dirname "$F")"; curl -fsSL -z "$F" "$U" -o "$F" 2>/dev/null || :; }
[ -r "$F" ] || { echo "missing tinyorch install script" >&2; exit 1; }
. "$F"

export JOB=zetronix-lark-zshades-2k-nash
export NOTIFY=jsons://homeassistant.0819870.xyz/api/webhook/-xfbKQcnt6wIwYvmFAwXQ1umd
export ARCHIVE_ROOT="$HOME/archive"
export TZ=America/Los_Angeles

export SOURCE=$(cat <<'EOF'
[remote]
type = local
global.transfers = 1
global.checkers = 2
global.multi_thread_streams = 0
global.buffer_size = 16M
EOF
)

export UPLOAD=$(cat <<EOF
[smb]
type = smb
host = 0819870.xyz
user = ns
pass = $(docker run --rm rclone/rclone obscure "$(get-password 'smb.0819870.xyz')")

[remote]
type = alias
remote = smb:shared/family/daily
EOF
)

if [ "${1:-}" = "-r" ]; then
  [ -n "${2:-}" ] || { echo "resume mode requires TIMESTAMP" >&2; exit 1; }
  export RUN_MODE=resume
  export RUN_TS="$2"
  export RUN_TARGET=
  DISPLAY_TARGET="$2"
else
  [ -n "${1:-}" ] || { echo "usage: $0 TARGET | $0 -r TIMESTAMP" >&2; exit 1; }
  export RUN_MODE=start
  export RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
  export RUN_TARGET="$1"
  DISPLAY_TARGET="$1"
fi

prompt-enter "Press ENTER to $RUN_MODE $JOB (${DISPLAY_TARGET})... "
keep-awake $$

eval "$(ensure-docker-host $$)"
export DOCKER_HOST DOCKER_SOCKET DOCKER

: "${TEST_SCRIPT:=}"
S=${TEST_SCRIPT:-https://raw.githubusercontent.com/nashspence/zetronix-lark-zshades-2k/main/zetronix-lark-zshades-2k.py}
if [ -n "$TEST_SCRIPT" ]; then python "$S"; else curl -fsSL "$S" | python -; fi
