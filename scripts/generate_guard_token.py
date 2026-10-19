#!/usr/bin/env python3
"""Generate a Guard-AI administrator token.

By default the seed is requested through a hidden prompt so it is not saved in
shell history. The same seed always produces the same token.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import secrets
import sys


TOKEN_BYTES = 32
MIN_SEED_LENGTH = 20
PBKDF2_ITERATIONS = 600_000
DERIVATION_CONTEXT = b"Guard-AI/GUARD_ADMIN_TOKEN/v1"


def derive_token(seed: str) -> str:
    """Derive a deterministic 256-bit token from a secret seed."""
    if len(seed) < MIN_SEED_LENGTH:
        raise ValueError(
            f"Seed must contain at least {MIN_SEED_LENGTH} characters. "
            "Use several random words or a password-manager-generated value."
        )

    token = hashlib.pbkdf2_hmac(
        "sha256",
        seed.encode("utf-8"),
        DERIVATION_CONTEXT,
        PBKDF2_ITERATIONS,
        dklen=TOKEN_BYTES,
    )
    return token.hex()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a 256-bit GUARD_ADMIN_TOKEN."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--seed",
        help="derive from this seed (visible in shell history; hidden prompt is safer)",
    )
    source.add_argument(
        "--seed-env",
        metavar="NAME",
        help="derive from the seed stored in environment variable NAME",
    )
    source.add_argument(
        "--random",
        action="store_true",
        help="generate a new random token instead of deriving one from a seed",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="print only the token instead of a dotenv assignment",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.random:
            token = secrets.token_hex(TOKEN_BYTES)
        else:
            if args.seed_env:
                seed = os.environ.get(args.seed_env)
                if seed is None:
                    raise ValueError(
                        f"Environment variable {args.seed_env!r} is not set."
                    )
            elif args.seed is not None:
                seed = args.seed
            else:
                seed = getpass.getpass("Guard-AI secret seed: ")

            token = derive_token(seed)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(token if args.raw else f"GUARD_ADMIN_TOKEN={token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
