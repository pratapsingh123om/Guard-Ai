#!/bin/sh
set -eu

FORCE="${1:-}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEMO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RUNTIME_ROOT="$DEMO_ROOT/runtime"
CERT_ROOT="$RUNTIME_ROOT/certs"
TOKEN_ROOT="$RUNTIME_ROOT/tokens"
SERVER_EXT="$DEMO_ROOT/pki/server.ext"
CLIENT_EXT="$DEMO_ROOT/pki/client.ext"

if [ -e "$CERT_ROOT" ] || [ -e "$TOKEN_ROOT" ]; then
    if [ "$FORCE" != "--force" ]; then
        echo "Runtime material exists; re-run with --force to replace demo-only files." >&2
        exit 1
    fi
    case "$RUNTIME_ROOT" in
        "$DEMO_ROOT/runtime") rm -rf -- "$CERT_ROOT" "$TOKEN_ROOT" ;;
        *) echo "Unexpected cleanup target: $RUNTIME_ROOT" >&2; exit 1 ;;
    esac
fi

mkdir -p "$CERT_ROOT/interop" "$CERT_ROOT/strict" "$TOKEN_ROOT"

generate_ecdsa_profile() {
    profile="$CERT_ROOT/interop"
    openssl ecparam -genkey -name secp384r1 -out "$profile/ca.key"
    openssl req -x509 -new -key "$profile/ca.key" -sha384 -days 1 -out "$profile/ca.crt" \
        -subj '/CN=Guard-AI Demo Interop CA' -addext 'basicConstraints=critical,CA:TRUE' \
        -addext 'keyUsage=critical,keyCertSign,cRLSign'
    openssl ecparam -genkey -name secp384r1 -out "$profile/server.key"
    openssl req -new -key "$profile/server.key" -sha384 -out "$profile/server.csr" -subj '/CN=guard-ai.demo'
    openssl x509 -req -in "$profile/server.csr" -CA "$profile/ca.crt" -CAkey "$profile/ca.key" \
        -CAcreateserial -days 1 -sha384 -extfile "$SERVER_EXT" -out "$profile/server.crt"
    openssl ecparam -genkey -name secp384r1 -out "$profile/client.key"
    openssl req -new -key "$profile/client.key" -sha384 -out "$profile/client.csr" -subj '/CN=coordinator-agent'
    openssl x509 -req -in "$profile/client.csr" -CA "$profile/ca.crt" -CAkey "$profile/ca.key" \
        -CAcreateserial -days 1 -sha384 -extfile "$CLIENT_EXT" -out "$profile/client.crt"
    rm -f -- "$profile/server.csr" "$profile/client.csr"
}

generate_mldsa_profile() {
    profile="$CERT_ROOT/strict"
    openssl genpkey -algorithm ML-DSA-65 -out "$profile/ca.key"
    openssl req -x509 -new -key "$profile/ca.key" -days 1 -out "$profile/ca.crt" \
        -subj '/CN=Guard-AI Demo Strict PQC CA' -addext 'basicConstraints=critical,CA:TRUE' \
        -addext 'keyUsage=critical,keyCertSign,cRLSign'
    openssl genpkey -algorithm ML-DSA-65 -out "$profile/server.key"
    openssl req -new -key "$profile/server.key" -out "$profile/server.csr" -subj '/CN=guard-ai.demo'
    openssl x509 -req -in "$profile/server.csr" -CA "$profile/ca.crt" -CAkey "$profile/ca.key" \
        -CAcreateserial -days 1 -extfile "$SERVER_EXT" -out "$profile/server.crt"
    openssl genpkey -algorithm ML-DSA-65 -out "$profile/client.key"
    openssl req -new -key "$profile/client.key" -out "$profile/client.csr" -subj '/CN=coordinator-agent'
    openssl x509 -req -in "$profile/client.csr" -CA "$profile/ca.crt" -CAkey "$profile/ca.key" \
        -CAcreateserial -days 1 -extfile "$CLIENT_EXT" -out "$profile/client.crt"
    rm -f -- "$profile/server.csr" "$profile/client.csr"
}

generate_ecdsa_profile
generate_mldsa_profile
openssl ecparam -genkey -name prime256v1 -out "$TOKEN_ROOT/issuer-private.pem"
openssl pkey -in "$TOKEN_ROOT/issuer-private.pem" -pubout -out "$TOKEN_ROOT/issuer-public.pem"

chmod 600 "$CERT_ROOT"/*/*.key "$TOKEN_ROOT/issuer-private.pem"
echo "Generated demo-only PKI under $RUNTIME_ROOT"
