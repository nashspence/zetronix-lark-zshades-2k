#!/bin/sh
U=https://raw.githubusercontent.com/nashspence/tinyorch/main/tinyorch.sh
F=$HOME/.local/tinyorch-lib.sh
mkdir -p "$HOME/.local"
curl -fsSL -z "$F" "$U" -o "$F" 2>/dev/null || :
[ -r "$F" ] || { echo "missing lib" >&2; exit 1; }
. "$F"
eval "$(ensure_docker_host $$)"
export DOCKER_HOST DOCKER_SOCKET DOCKER

export JOB=zetronix-lark-zshades-2k
export NOTIFY=jsons://homeassistant.local/api/webhook/<your-webhook-id>
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
host = smb.local
user = example
pass = $(docker run --rm rclone/rclone obscure "$(pw 'smb.local')")

[remote]
type = alias
remote = smb:<your-share>/$JOB
EOF
)

S=${TEST_SCRIPT:-https://raw.githubusercontent.com/nashspence/zetronix-lark-zshades-2k/main/zetronix-lark-zshades-2k.py}
if [ -n "$TEST_SCRIPT" ]; then python "$S" "$@"; else curl -fsSL "$S" | python - "$@"; fi
