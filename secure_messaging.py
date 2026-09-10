"""Authenticated one-time-pad messaging using QKD-derived bits.

This module treats the QKD sifted key as a finite resource: it must contain
one fresh bit for every plaintext bit, plus a separate authentication key.
Keys are never cycled or reused.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Sequence


AUTH_KEY_BITS = 128
PACKAGE_FORMAT = "qkd-otp-message-v1"


def _validate_bits(bits: Sequence[int]) -> list[int]:
    normalized = [int(bit) for bit in bits]
    if any(bit not in (0, 1) for bit in normalized):
        raise ValueError("QKD keys may contain only 0 and 1 bits.")
    return normalized


def _bits_to_bytes(bits: Sequence[int]) -> bytes:
    if len(bits) % 8:
        raise ValueError("Authentication key length must be a whole number of bytes.")
    return bytes(
        int("".join(str(bit) for bit in bits[index:index + 8]), 2)
        for index in range(0, len(bits), 8)
    )


def _auth_message(protocol: str, ciphertext: str, message_length_bytes: int) -> bytes:
    return f"{PACKAGE_FORMAT}|{protocol}|{message_length_bytes}|{ciphertext}".encode("ascii")


def _tag(auth_key: bytes, protocol: str, ciphertext: str, message_length_bytes: int) -> str:
    return hmac.new(
        auth_key,
        _auth_message(protocol, ciphertext, message_length_bytes),
        hashlib.sha256,
    ).hexdigest()


def encrypt_message(message: str, key_bits: Sequence[int], protocol: str) -> dict[str, Any]:
    """Encrypt and authenticate a UTF-8 message with fresh QKD key bits."""
    normalized_key = _validate_bits(key_bits)
    plaintext = message.encode("utf-8")
    required_bits = len(plaintext) * 8 + AUTH_KEY_BITS
    if len(normalized_key) < required_bits:
        raise ValueError(
            f"QKD key is too short: need {required_bits} bits, "
            f"but only {len(normalized_key)} survived sifting."
        )

    otp_bits = normalized_key[:len(plaintext) * 8]
    auth_bits = normalized_key[len(plaintext) * 8:required_bits]
    ciphertext_bytes = bytes(
        plaintext[index] ^ int("".join(str(bit) for bit in otp_bits[index * 8:(index + 1) * 8]), 2)
        for index in range(len(plaintext))
    )
    ciphertext = base64.b64encode(ciphertext_bytes).decode("ascii")
    auth_key = _bits_to_bytes(auth_bits)
    return {
        "format": PACKAGE_FORMAT,
        "protocol": protocol,
        "message_length_bytes": len(plaintext),
        "key_bits_used": required_bits,
        "ciphertext": ciphertext,
        "tag": _tag(auth_key, protocol, ciphertext, len(plaintext)),
    }


def decrypt_message(package: dict[str, Any], key_bits: Sequence[int], protocol: str) -> str:
    """Verify and decrypt a package with the receiver's fresh QKD key bits."""
    if package.get("format") != PACKAGE_FORMAT:
        raise ValueError("Unsupported or invalid message package format.")
    if package.get("protocol") != protocol:
        raise ValueError("The message package and QKD key use different protocols.")

    message_length = int(package["message_length_bytes"])
    required_bits = message_length * 8 + AUTH_KEY_BITS
    normalized_key = _validate_bits(key_bits)
    if len(normalized_key) < required_bits:
        raise ValueError("The receiver key is too short for this message package.")

    ciphertext = str(package["ciphertext"])
    expected_tag = _tag(
        _bits_to_bytes(normalized_key[message_length * 8:required_bits]),
        protocol,
        ciphertext,
        message_length,
    )
    if not hmac.compare_digest(expected_tag, str(package.get("tag", ""))):
        raise ValueError("Authentication failed: the package or key was modified.")

    try:
        ciphertext_bytes = base64.b64decode(ciphertext, validate=True)
    except Exception as error:
        raise ValueError("The ciphertext is not valid base64.") from error
    if len(ciphertext_bytes) != message_length:
        raise ValueError("The ciphertext length does not match the package metadata.")

    otp_bits = normalized_key[:message_length * 8]
    plaintext = bytes(
        ciphertext_bytes[index] ^ int("".join(str(bit) for bit in otp_bits[index * 8:(index + 1) * 8]), 2)
        for index in range(message_length)
    )
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Decryption produced invalid UTF-8; the key may be incorrect.") from error


def package_json(package: dict[str, Any]) -> str:
    """Serialize a package consistently for download or transfer."""
    return json.dumps(package, indent=2)
