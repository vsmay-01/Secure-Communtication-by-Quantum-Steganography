# Quantum Steganography

Hide a secret text message inside an ordinary "cover" sentence, protected by
a shared secret key generated with real **Quantum Key Distribution (QKD)**
protocols — **BB84**, **BBM92**, and **Ekert91** — simulated using
[Qiskit](https://www.ibm.com/quantum/qiskit).

## Idea

```
Cover Sentence (X) ----.
                        v
Secret Message (M) -> Encryption (XOR with QKD key K) -> Cipher bits
                                                              |
                                                              v
                                            Steganographic Encode f(X, M, K)
                                                              |
                                                              v
                                                       Stego Sentence
                                                              |
                                                (sent over a public channel)
```

An eavesdropper who intercepts the stego sentence just sees ordinary text
with odd capitalization — without the QKD-derived key `K`, the hidden
message cannot be recovered.

## How it works

1. **Key generation (quantum):** Alice and Bob run a QKD protocol over a
   simulated quantum channel. Depending on which bases/angles happen to
   match, a subset of their raw bits becomes the **sifted key** — a string
   of bits only the two of them know.
2. **Encryption:** The secret message is converted to bits and XORed with
   the (cycled) QKD key.
3. **Steganographic encoding:** Each encrypted bit is hidden in the cover
   sentence using **letter case** — an uppercase letter encodes `1`, a
   lowercase letter encodes `0`. Punctuation and spaces are untouched.
4. **Decoding:** Bob reads the case pattern back into bits, XORs with his
   copy of the QKD key, and recovers the original message.

## Project layout

| File                    | Purpose                                                            |
|-------------------------|---------------------------------------------------------------------|
| `qkd_protocols.py`      | BB84, BBM92, and Ekert91 QKD simulations (Qiskit circuits)          |
| `steganography.py`      | Encrypt/decrypt + hide/reveal bits in cover text via letter case    |
| `noisy_backend.py`      | A noisy simulator (gate + readout errors) standing in for real hardware, plus an ideal backend |
| `compare_protocols.py`  | Generates comparison plots: ideal vs. noisy backend, per protocol   |
| `main.py`               | Command-line, end-to-end interactive demo                          |
| `app.py`                | Streamlit graphical interactive demo (slider, buttons, live circuit view) |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the console demo

```bash
python3 main.py
```

You'll be asked to:
1. Pick a protocol (BB84 / BBM92 / Ekert91) and number of qubits (try 7).
2. Enter a secret message (e.g. `bnmit`).
3. Enter a cover sentence long enough to carry the encrypted bits
   (needs at least `8 × len(secret message)` letters).

It prints the generated key, the stego sentence, and the recovered
message.

## Run the interactive graphical app

```bash
streamlit run app.py
```

This opens a browser UI with:
- A protocol selector and a qubit-count slider.
- A live view of the quantum circuit used.
- The generated Alice/Bob bases and sifted keys, with QBER.
- Text boxes to enter your secret message and cover sentence, and
  Encrypt / Decode buttons.
- A "Compare Simulators" tab showing ideal-vs-noisy QBER across all three
  protocols.

## Generate comparison plots (like a research report)

```bash
python3 compare_protocols.py
```

Saves PNGs to `./output/`:
- `comparison_bb84.png`, `comparison_bbm92.png`, `comparison_ekert91.png` —
  Alice/Bob sifted-key bit distributions, ideal vs. noisy backend.
- `qber_summary.png` — a single bar chart of QBER across all protocols.

## Notes on the noisy backend

The reference project used IBM's `FakeWashingtonV2()` mock backend (part of
`qiskit-ibm-runtime`) to simulate a real, noisy quantum computer. To keep
this project's dependencies light, `noisy_backend.py` builds an equivalent
custom noise model (depolarizing gate errors + readout errors) with
`qiskit-aer`'s `NoiseModel`. If you have `qiskit-ibm-runtime` installed,
you can swap in the real fake backend via
`noisy_backend.get_real_fake_backend()`.

## Extending this project

- **Bigger alphabet:** hide bits using more than 1 bit/letter (e.g. via
  whitespace or homoglyph substitution) to shrink the required cover text.
- **Real Bell test:** Ekert91's "extra" (non-matching) analyzer-angle
  measurements can be used to compute a CHSH S-value and detect
  eavesdroppers — `qkd_protocols.py` already records enough raw data to
  extend this.
- **Real hardware:** swap the Aer simulator for an actual IBM Quantum
  backend via Qiskit Runtime to see real-world QBER.
