#!/bin/sh
set -eu

EXPECTED_GROUP="${GUARD_MCP_TLS_GROUP:-X25519MLKEM768}"
nginx_pid=""

openssl version
if ! openssl list -tls1_3 -tls-groups | tr ':' '\n' | grep -qx "$EXPECTED_GROUP"; then
    echo "Required TLS group is unavailable: $EXPECTED_GROUP" >&2
    exit 1
fi

nginx -V 2>&1 | grep -q -- '--with-http_ssl_module'
nginx -e /dev/stderr -t

mkdir -p /run/guard-ai
rm -f /run/guard-ai/backend.sock

uvicorn backend.app.main:app \
    --uds /run/guard-ai/backend.sock \
    --proxy-headers \
    --forwarded-allow-ips=127.0.0.1 &
backend_pid=$!

cleanup() {
    kill "$backend_pid" 2>/dev/null || true
    [ -z "$nginx_pid" ] || kill "$nginx_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

for _ in $(seq 1 900); do
    [ -S /run/guard-ai/backend.sock ] && break
    kill -0 "$backend_pid" 2>/dev/null || {
        echo "Guard-AI backend exited during startup" >&2
        exit 1
    }
    sleep 0.1
done
[ -S /run/guard-ai/backend.sock ] || {
    echo "Guard-AI backend socket was not created" >&2
    exit 1
}
# The socket lives in a private container tmpfs and is the only path from the
# unprivileged Nginx worker to the backend process.
chmod 771 /run/guard-ai
chmod 666 /run/guard-ai/backend.sock

nginx -e /dev/stderr -g 'daemon off;' &
nginx_pid=$!

while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

echo "A Guard-AI demo process exited unexpectedly" >&2
exit 1
