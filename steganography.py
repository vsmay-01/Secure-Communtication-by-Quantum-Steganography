"""
steganography.py
------------------
Quantum-key-based text steganography.

Pipeline (matches the Abstract/diagram of the reference project):

    Cover File (x) ----.
                        v
    Secret Message (M) -> Encryption Algorithm -> Cipher Text
                                                        |
                                                        v
                                        Steganographic Encode f(X, M, K)
                                                        |
                                                        v
                                              Stego Object  --> sent over channel

The "Keys" (K) come from a QKD protocol (BB84 / BBM92 / Ekert91), so an
eavesdropper who doesn't share the quantum-derived key cannot recover the
secret message even if they intercept the stego object.

Encoding scheme
----------------
1. The secret message M is converted to bits (8 bits/char, ASCII).
2. Those bits are XORed with the QKD key K (repeated/cycled to length) to
   produce a cipher bit-stream -> this is the "encryption" step.
3. The cipher bits are hidden inside the cover sentence using a simple,
   human-visible carrier: each alphabetic character of the cover text
   carries one bit via its *letter case* (uppercase = 1, lowercase = 0).
   Non-alphabetic characters (spaces, punctuation) are left untouched and
   carry no bit, so they don't disturb decoding.
4. Decoding reverses the process: read the case pattern of the stego text
   back into cipher bits, XOR with the same key K, and rebuild the
   original ASCII message.

This mirrors the reference project's console flow: enter number of qubits
-> generate QKD key -> enter secret message -> enter cover sentence ->
Encrypt -> Decode.
"""

from __future__ import annotations
from typing import List


# --------------------------------------------------------------------------
# Bit <-> text helpers
# --------------------------------------------------------------------------

def text_to_bits(text: str) -> List[int]:
    bits = []
    for ch in text.encode("utf-8"):
        bits.extend(int(b) for b in format(ch, "08b"))
    return bits


def bits_to_text(bits: List[int]) -> str:
    # Truncate to a whole number of bytes
    n_bytes = len(bits) // 8
    byte_vals = []
    for i in range(n_bytes):
        byte_bits = bits[i * 8:(i + 1) * 8]
        byte_vals.append(int("".join(str(b) for b in byte_bits), 2))
    try:
        return bytes(byte_vals).decode("utf-8", errors="replace")
    except Exception:
        return "".join(chr(b) for b in byte_vals)


def _cycle_key(key_bits: List[int], length: int) -> List[int]:
    if not key_bits:
        raise ValueError("QKD key is empty — generate a longer key (more qubits) first.")
    return [key_bits[i % len(key_bits)] for i in range(length)]


# --------------------------------------------------------------------------
# "Encryption" step: XOR the message bits with the quantum key
# --------------------------------------------------------------------------

def encrypt_message(message: str, key_bits: List[int]) -> List[int]:
    """XOR the message's bits with the (cycled) quantum-derived key."""
    msg_bits = text_to_bits(message)
    key_cycled = _cycle_key(key_bits, len(msg_bits))
    return [m ^ k for m, k in zip(msg_bits, key_cycled)]


def decrypt_message(cipher_bits: List[int], key_bits: List[int]) -> str:
    key_cycled = _cycle_key(key_bits, len(cipher_bits))
    msg_bits = [c ^ k for c, k in zip(cipher_bits, key_cycled)]
    return bits_to_text(msg_bits)


# --------------------------------------------------------------------------
# Steganographic encode/decode: hide cipher bits in letter-case pattern
# --------------------------------------------------------------------------

def capacity(cover_text: str) -> int:
    """How many bits (= how many alphabetic characters) the cover text can carry."""
    return sum(1 for ch in cover_text if ch.isalpha())


def stego_encode(cover_text: str, cipher_bits: List[int]) -> str:
    """
    Hide `cipher_bits` inside `cover_text` using letter case:
    uppercase letter -> bit 1, lowercase letter -> bit 0.
    Non-alphabetic characters pass through unchanged and carry no bit.
    Raises if the cover text is too short to carry all the cipher bits.
    """
    cap = capacity(cover_text)
    if len(cipher_bits) > cap:
        raise ValueError(
            f"Cover text can only carry {cap} bits, but the encrypted "
            f"message needs {len(cipher_bits)} bits. Use a longer cover "
            f"sentence or a shorter secret message."
        )

    out_chars = []
    bit_iter = iter(cipher_bits)
    for ch in cover_text:
        if ch.isalpha():
            bit = next(bit_iter, None)
            if bit is None:
                # No more bits to hide; keep letter as-is (lowercase for consistency)
                out_chars.append(ch.lower())
            else:
                out_chars.append(ch.upper() if bit == 1 else ch.lower())
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def stego_decode_bits(stego_text: str, n_bits: int) -> List[int]:
    """Extract the first `n_bits` hidden bits from a stego text's letter-case pattern."""
    bits = []
    for ch in stego_text:
        if ch.isalpha():
            bits.append(1 if ch.isupper() else 0)
            if len(bits) == n_bits:
                break
    if len(bits) < n_bits:
        raise ValueError("Stego text does not contain enough letters to recover the message.")
    return bits


# --------------------------------------------------------------------------
# End-to-end convenience functions
# --------------------------------------------------------------------------

def encode(cover_text: str, secret_message: str, key_bits: List[int]) -> str:
    """Full pipeline: encrypt secret_message with key_bits, then hide in cover_text."""
    cipher_bits = encrypt_message(secret_message, key_bits)
    return stego_encode(cover_text, cipher_bits)


def decode(stego_text: str, secret_message_len_chars: int, key_bits: List[int]) -> str:
    """Full pipeline: extract cipher bits from stego_text, then decrypt with key_bits."""
    n_bits = secret_message_len_chars * 8
    cipher_bits = stego_decode_bits(stego_text, n_bits)
    return decrypt_message(cipher_bits, key_bits)


if __name__ == "__main__":
    # Quick self-test
    key = [0, 1, 1, 0, 1, 1, 0]  # a short demo "QKD" key
    secret = "hi"
    cover = "Bangalore is known as the silicon city of india"

    print("Capacity of cover text (bits):", capacity(cover))
    stego = encode(cover, secret, key)
    print("Stego text:", stego)

    recovered = decode(stego, len(secret), key)
    print("Recovered secret:", recovered)
    assert recovered == secret, "Round trip failed!"
    print("Round-trip OK ✅")
