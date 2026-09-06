"""
main.py
--------
Command-line, end-to-end demo of Quantum Steganography:

    1. Pick a QKD protocol (BB84 / BBM92 / Ekert91) and number of qubits.
    2. Run the protocol on a quantum simulator to get a shared secret key
       between "Alice" and "Bob".
    3. Alice encrypts her secret message with the key (XOR) and hides the
       result inside a cover sentence using a text-steganography scheme.
    4. Bob receives the stego sentence, extracts the hidden bits, and
       decrypts them with the (separately, securely shared) QKD key to
       recover the original secret message.

Run it with:  python3 main.py
"""

from qkd_protocols import run_protocol, PROTOCOLS
from steganography import encode, decode, capacity, encrypt_message


def choose_protocol() -> str:
    print("Choose a QKD protocol to generate the shared secret key:")
    names = list(PROTOCOLS.keys())
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    while True:
        choice = input(f"Enter 1-{len(names)} [default 1=BB84]: ").strip()
        if choice == "":
            return names[0]
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return names[int(choice) - 1]
        print("Invalid choice, try again.")


def choose_qubits() -> int:
    while True:
        raw = input("Number of qubits / entangled pairs to use (try 7): ").strip()
        if raw == "":
            return 7
        if raw.isdigit() and int(raw) >= 1:
            return int(raw)
        print("Please enter a positive integer.")


def main():
    print("=" * 60)
    print(" QUANTUM STEGANOGRAPHY — interactive console demo")
    print("=" * 60)

    protocol_name = choose_protocol()
    n_qubits = choose_qubits()

    print(f"\nRunning {protocol_name} with {n_qubits} qubits/pairs on the Aer simulator...")
    result = run_protocol(protocol_name, n_qubits, seed=None)

    print(f"\nAlice's bases : {result.alice_bases}")
    print(f"Bob's bases   : {result.bob_bases}")
    print(f"Alice key     : {result.key_string_alice}")
    print(f"Bob key       : {result.key_string_bob}")
    print(f"QBER          : {result.qber:.3f}  (0.0 = perfectly matching keys)")

    if not result.alice_key:
        print("\nNo bits survived sifting — try again with more qubits.")
        return

    key_bits = result.alice_key  # the shared secret key both parties hold

    secret_message = input("\nEnter the secret message to hide (small letters, e.g. 'hi'): ").strip()
    if not secret_message:
        secret_message = "hi"

    while True:
        cover_text = input("Enter the carrier/cover sentence: ").strip()
        needed_bits = len(secret_message.encode("utf-8")) * 8
        cap = capacity(cover_text) if cover_text else 0
        if cover_text and cap >= needed_bits:
            break
        print(f"  Cover sentence needs at least {needed_bits} letters "
              f"(it currently has {cap}). Try a longer sentence.")

    stego_text = encode(cover_text, secret_message, key_bits)
    print(f"\nEncoded (stego) text sent over the channel:\n  {stego_text}")

    recovered = decode(stego_text, len(secret_message), key_bits)
    print(f"\nBob decodes using the shared QKD key -> recovered secret message:\n  {recovered}")

    if recovered == secret_message:
        print("\n✅ Success — secret message recovered exactly, hidden in plain sight!")
    else:
        print("\n⚠️  Mismatch — this can happen if quantum noise corrupted a few key "
              "bits (see QBER above). Try more qubits or run again.")


if __name__ == "__main__":
    main()
