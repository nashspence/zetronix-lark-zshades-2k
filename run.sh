#!/bin/sh

set -eu; set -o pipefail 2>/dev/null || true

U=https://raw.githubusercontent.com/nashspence/tinyorch/main/lib.sh
F=$HOME/.local/tinyorch-lib.sh
mkdir -p "$HOME/.local"
curl -fsSL -z "$F" "$U" -o "$F" 2>/dev/null || :
[ -r "$F" ] || { echo "missing lib" >&2; exit 1; }
. "$F"

eval "$(ensure_docker_host $$)"; export DOCKER_HOST DOCKER_SOCKET

: "${ARCHIVE_ROOT:?}"
: "${IMAGE:?}"
: "${JOB:?}"
: "${NOTIFY:?}"
: "${SOURCE:?}"
: "${TZ:?}"
: "${UPLOAD:?}"

[ "$1" = "-r" ] && MODE=resume TARGET=$2 || MODE=start TARGET=$1
if [ "$MODE" = "start" ]; then
  TS=$(date -u +%Y%m%dT%H%M%SZ)
else
  TS="$TARGET"
fi

RUN_DIR="${ARCHIVE_ROOT}/${JOB}/${TS}"
ISO_DIR="${RUN_DIR}/make_iso"
ISO_PATH="${ISO_DIR}/${TS}.iso"

prompt_enter "Press ENTER to $MODE $JOB ($TARGET)... "

keep_awake

if [ -n "${TEST:-}" ]; then
  docker buildx build --no-cache --load -t "$JOB" "$TEST"
  IMAGE="$JOB"
fi

mkdir -p "$ARCHIVE_ROOT"
mkdir -p "$ISO_DIR"

(
  wait_for_files 5 "$RUN_DIR/.make_iso.done" "$ISO_PATH"
  run "burn_iso" -1 "Burn complete" burn_iso "$ISO_PATH"
) &
BURN_PID=$!

docker run --rm -it \
  --security-opt label=disable \
  --name "${JOB}" \
  --hostname "${JOB}" \
  $SIDECAR_ENV_ARG \
  -e DOCKER_HOST="unix:///var/run/docker.sock" \
  -e JOB="$JOB" \
  -e MODE="$MODE" \
  -e NOTIFY="$NOTIFY" \
  -e RUN_DIR="$RUN_DIR" \
  -e SOURCE="$SOURCE" \
  -e TARGET="$TARGET" \
  -e TZ="$TZ" \
  -e UPLOAD="$UPLOAD" \
  -e ISO_PATH="$ISO_PATH" \
  -v "$DOCKER_SOCKET:/var/run/docker.sock" \
  -v "$RUN_DIR:$RUN_DIR" \
  "$IMAGE"
  
status=$?

wait "$BURN_PID" || true
exit "$status"
