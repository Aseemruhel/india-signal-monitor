#!/usr/bin/env python3
"""
India Pulse 360 — Dashboard Content Encryption
Encrypts data/summary.json and data/topics.json with AES-256-GCM,
keyed by a PBKDF2-derived key from a shared passphrase, so the
published JSON is unreadable without the password.

Decryption happens entirely client-side in the browser via the
Web Crypto API (see decrypt.js). This script never embeds the
passphrase anywhere in the output — only the salt/iv/ciphertext
are written, all of which are useless without the password.

The passphrase itself is read from an environment variable
(DASHBOARD_PASSWORD) so it is never committed to the repo. In
GitHub Actions, set this as a repository secret and pass it in
via `env:` — see the workflow snippet in SETUP.md.

Requires: pip install cryptography
"""

import os
import json
import base64
import secrets
import sys

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Parameters — MUST match decrypt.js exactly ─────────────────────────────
PBKDF2_ITERATIONS = 250_000   # cost factor; higher = slower brute force
SALT_LEN_BYTES     = 16
IV_LEN_BYTES        = 12       # 96-bit nonce, standard for AES-GCM
KEY_LEN_BYTES       = 32       # AES-256


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LEN_BYTES,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_file(in_path: str, out_path: str, passphrase: str) -> None:
    if not os.path.exists(in_path):
        print(f"  ⚠ {in_path} not found — skipping")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        plaintext = f.read().encode("utf-8")

    salt = secrets.token_bytes(SALT_LEN_BYTES)
    iv = secrets.token_bytes(IV_LEN_BYTES)
    key = derive_key(passphrase, salt)

    # AESGCM.encrypt() returns ciphertext with the 16-byte auth tag
    # appended — this matches what Web Crypto's subtle.decrypt expects
    # on the browser side, so no extra tag-handling is needed anywhere.
    ciphertext = AESGCM(key).encrypt(iv, plaintext, None)

    payload = {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    print(f"  ✓ {in_path} -> {out_path}  ({len(plaintext)} bytes plaintext -> {len(ciphertext)} bytes ciphertext)")


def main():
    passphrase = os.environ.get("DASHBOARD_PASSWORD")
    if not passphrase:
        print("✗ DASHBOARD_PASSWORD environment variable is not set.")
        print("  Set it as a GitHub Actions secret, or export it locally for testing.")
        sys.exit(1)

    if len(passphrase) < 12:
        print("⚠ Warning: passphrase is shorter than 12 characters.")
        print("  Since this is a single shared password protecting an offline-")
        print("  attackable ciphertext, use a long, random passphrase —")
        print("  e.g. 4-5 random words, not a dictionary word or short phrase.")

    print("Encrypting dashboard data files...")
    encrypt_file("data/summary.json", "data/summary.enc.json", passphrase)
    encrypt_file("data/topics.json", "data/topics.enc.json", passphrase)
    print("Done.")


if __name__ == "__main__":
    main()
