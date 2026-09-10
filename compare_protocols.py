"""
compare_protocols.py
----------------------
Reproduces the "Future Scopes and Improvements" comparison charts from the
reference project: for each QKD protocol (BB84, BBM92, Ekert91), plot the
sifted-key bit distribution obtained on:

    (a) an ideal, noise-free simulator ('qasm_simulator' equivalent), and
    (b) a noisy simulator standing in for a real device ('FakeWashingtonV2').

On the ideal simulator, Alice and Bob's keys agree bit-for-bit (clean bars).
On the noisy backend, gate/readout errors introduce a non-trivial spread of
outcomes (QBER > 0), which is what the "difference" the original project
points out looks like.

Produces one PNG per protocol plus a summary QBER bar chart, saved to
./output/.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from qkd_protocols import run_protocol, PROTOCOLS
from noisy_backend import get_ideal_backend, build_noisy_backend

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Colors matching the reference project's palette (orange/pink/purple/gold/blue)
PALETTE = ["#f4923b", "#e0417c", "#8a6de0", "#f0a83c", "#5b8fe0"]


def _bit_distribution(key_bits):
    """Return counts of '0' and '1' in a sifted key (for a simple bar chart)."""
    zeros = key_bits.count(0)
    ones = key_bits.count(1)
    return zeros, ones


def plot_protocol_comparison(protocol_name: str, n_qubits: int = 40, trials: int = 1):
    """
    Run `protocol_name` on both the ideal and noisy backend and save a
    side-by-side bar chart of the resulting sifted-key bit distributions,
    mirroring the reference project's 'qasm_simulator vs FakeWashingtonV2'
    comparison figures.
    """
    ideal_backend = get_ideal_backend()
    noisy_backend = build_noisy_backend()

    ideal_result = run_protocol(protocol_name, n_qubits, backend=ideal_backend, seed=1)
    noisy_result = run_protocol(protocol_name, n_qubits, backend=noisy_backend, seed=1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for ax, result, title in [
        (axes[0], ideal_result, f"{protocol_name} — qasm_simulator (ideal)"),
        (axes[1], noisy_result, f"{protocol_name} — FakeWashingtonV2 (noisy)"),
    ]:
        z, o = _bit_distribution(result.alice_key)
        z_b, o_b = _bit_distribution(result.bob_key)
        x = np.arange(2)
        width = 0.35
        ax.bar(x - width / 2, [z, o], width, label="Alice key", color=PALETTE[0])
        ax.bar(x + width / 2, [z_b, o_b], width, label="Bob key", color=PALETTE[2])
        ax.set_xticks(x)
        ax.set_xticklabels(["bit=0", "bit=1"])
        ax.set_ylabel("count")
        ax.set_title(title, fontsize=9)
        ax.legend(fontsize=7)
        ax.text(0.5, -0.28, f"QBER = {result.qber:.2f}   key len = {len(result.alice_key)}",
                 transform=ax.transAxes, ha="center", fontsize=8)

    fig.suptitle(f"Comparison results of `qasm_simulator` and `FakeWashingtonV2()` for {protocol_name} protocol")
    fig.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, f"comparison_{protocol_name.lower()}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path, ideal_result, noisy_result


def plot_qber_summary(n_qubits: int = 40):
    """Bar chart summarizing QBER (quantum bit error rate) for all 3 protocols,
    ideal vs. noisy — a compact 'headline' comparison chart."""
    ideal_backend = get_ideal_backend()
    noisy_backend = build_noisy_backend()

    names = list(PROTOCOLS.keys())
    ideal_qbers, noisy_qbers = [], []
    for name in names:
        # Ekert91's non-Clifford rotations + entangled pairs need smaller n
        n = n_qubits if name == "BB84" else max(8, n_qubits // 3)
        ideal_qbers.append(run_protocol(name, n, backend=ideal_backend, seed=2).qber)
        noisy_qbers.append(run_protocol(name, n, backend=noisy_backend, seed=2).qber)

    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - width / 2, ideal_qbers, width, label="Ideal (qasm_simulator)", color=PALETTE[4])
    ax.bar(x + width / 2, noisy_qbers, width, label="Noisy (FakeWashingtonV2)", color=PALETTE[1])
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Quantum Bit Error Rate (QBER)")
    ax.set_title("QBER across protocols: ideal vs. noisy simulation")
    ax.legend()
    fig.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "qber_summary.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    for name in PROTOCOLS:
        path, ideal_r, noisy_r = plot_protocol_comparison(name)
        print(f"Saved {path}  (ideal QBER={ideal_r.qber:.2f}, noisy QBER={noisy_r.qber:.2f})")
    summary_path = plot_qber_summary()
    print(f"Saved {summary_path}")
