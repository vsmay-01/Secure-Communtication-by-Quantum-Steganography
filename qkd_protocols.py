"""
qkd_protocols.py
-----------------
Implements three Quantum Key Distribution (QKD) protocols using Qiskit:

    1. BB84    - prepare-and-measure protocol (Bennett & Brassard, 1984)
    2. BBM92   - entanglement-based version of BB84 (Bennett, Brassard, Mermin, 1992)
    3. Ekert91 - entanglement-based protocol using CHSH-style bases (Ekert, 1991)

Each protocol returns a dictionary with the sifted keys for Alice and Bob,
their raw bases/bits, and the transpiled circuit used, so it can be
inspected/plotted by the caller (e.g. an interactive app).

These are *simulations* meant for learning/demoing quantum steganography.
They run on Qiskit Aer's statevector/qasm simulator, or optionally on a
noisy fake backend for realism comparisons.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


@dataclass
class QKDResult:
    protocol: str
    alice_bits: list           # Alice's raw random bits (or measurement outcomes)
    alice_bases: list          # Alice's basis choices (as human-readable symbols)
    bob_bits: list             # Bob's raw measurement outcomes
    bob_bases: list            # Bob's basis choices
    alice_key: list            # Sifted key (bits kept where bases matched)
    bob_key: list              # Sifted key (should equal alice_key, minus noise)
    circuit: Optional[QuantumCircuit] = None
    counts: Optional[dict] = field(default=None)

    @property
    def key_string_alice(self) -> str:
        return "".join(str(b) for b in self.alice_key)

    @property
    def key_string_bob(self) -> str:
        return "".join(str(b) for b in self.bob_key)

    @property
    def qber(self) -> float:
        """Quantum Bit Error Rate between the two sifted keys."""
        if not self.alice_key:
            return 0.0
        n = min(len(self.alice_key), len(self.bob_key))
        if n == 0:
            return 0.0
        mismatches = sum(1 for i in range(n) if self.alice_key[i] != self.bob_key[i])
        return mismatches / n


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _run_circuit(qc: QuantumCircuit, backend=None, shots: int = 1):
    """Transpile + run a single circuit, returning (transpiled_circuit, memory, counts)."""
    backend = backend or AerSimulator()
    tqc = transpile(qc, basis_gates=["h", "x", "cx", "ry", "rz", "measure"])
    job = backend.run(tqc, shots=shots, memory=True)
    result = job.result()
    memory = result.get_memory(tqc)
    counts = result.get_counts(tqc)
    return tqc, memory, counts


def _run_batch(circuits: list, backend=None, shots: int = 1):
    """
    Transpile + run a BATCH of small, independent circuits in one job.

    Each pair/qubit in BB84/BBM92/Ekert91 is physically independent, so
    rather than building one giant N-qubit register (which blows up
    statevector memory exponentially, especially once non-Clifford
    rotation gates are involved as in Ekert91), we simulate each pair as
    its own tiny circuit. This scales to hundreds of key-bits instead of
    only a couple dozen.
    """
    backend = backend or AerSimulator()
    tqcs = [transpile(qc, basis_gates=["h", "x", "cx", "ry", "rz", "measure"]) for qc in circuits]
    job = backend.run(tqcs, shots=shots, memory=True)
    result = job.result()
    memories = [result.get_memory(i) for i in range(len(tqcs))]
    return tqcs, memories


# --------------------------------------------------------------------------
# 1. BB84 - prepare and measure
# --------------------------------------------------------------------------

def bb84_protocol(n_qubits: int, backend=None, seed: Optional[int] = None) -> QKDResult:
    """
    Alice randomly picks a bit and a basis (Z or X) for each qubit, encodes it,
    sends it to Bob. Bob randomly picks a basis and measures. They keep only
    the bits where their bases matched (sifting).
    """
    rng = random.Random(seed)

    alice_bits = [rng.randint(0, 1) for _ in range(n_qubits)]
    alice_bases = [rng.choice(["Z", "X"]) for _ in range(n_qubits)]
    bob_bases = [rng.choice(["Z", "X"]) for _ in range(n_qubits)]

    circuits = []
    for i in range(n_qubits):
        qc = QuantumCircuit(1, 1, name=f"bb84_{i}")
        if alice_bits[i] == 1:
            qc.x(0)
        if alice_bases[i] == "X":
            qc.h(0)
        qc.barrier()
        if bob_bases[i] == "X":
            qc.h(0)
        qc.measure(0, 0)
        circuits.append(qc)

    tqcs, memories = _run_batch(circuits, backend=backend, shots=1)
    bob_bits = [int(m[0]) for m in memories]

    alice_key, bob_key = [], []
    for i in range(n_qubits):
        if alice_bases[i] == bob_bases[i]:
            alice_key.append(alice_bits[i])
            bob_key.append(bob_bits[i])

    # Keep one representative circuit (nicely illustrates the scheme) for display
    display_circuit = tqcs[0] if tqcs else None

    return QKDResult(
        protocol="BB84",
        alice_bits=alice_bits, alice_bases=alice_bases,
        bob_bits=bob_bits, bob_bases=bob_bases,
        alice_key=alice_key, bob_key=bob_key,
        circuit=display_circuit, counts=None,
    )


# --------------------------------------------------------------------------
# 2. BBM92 - entanglement-based BB84
# --------------------------------------------------------------------------

def bbm92_protocol(n_pairs: int, backend=None, seed: Optional[int] = None) -> QKDResult:
    """
    A source generates `n_pairs` Bell pairs. Alice holds one qubit of each
    pair, Bob the other. Both randomly choose a measurement basis (Z or X)
    for every pair and measure. Bases are compared publicly afterwards;
    matching-basis results form the sifted key. Thanks to entanglement,
    when bases match, results are perfectly (anti)correlated.
    """
    rng = random.Random(seed)
    n = n_pairs

    alice_bases = [rng.choice(["Z", "X"]) for _ in range(n)]
    bob_bases = [rng.choice(["Z", "X"]) for _ in range(n)]

    circuits = []
    for i in range(n):
        qc = QuantumCircuit(2, 2, name=f"bbm92_{i}")
        qc.h(0)
        qc.cx(0, 1)
        qc.barrier()
        if alice_bases[i] == "X":
            qc.h(0)
        if bob_bases[i] == "X":
            qc.h(1)
        qc.measure([0, 1], [0, 1])
        circuits.append(qc)

    tqcs, memories = _run_batch(circuits, backend=backend, shots=1)
    alice_bits, bob_bits = [], []
    for m in memories:
        bitstring = m[0][::-1]  # bitstring[0]=qubit0(Alice), bitstring[1]=qubit1(Bob)
        alice_bits.append(int(bitstring[0]))
        bob_bits.append(int(bitstring[1]))

    alice_key, bob_key = [], []
    for i in range(n):
        if alice_bases[i] == bob_bases[i]:
            alice_key.append(alice_bits[i])
            # Bell pair |Φ+> gives *equal* results in the same basis
            bob_key.append(bob_bits[i])

    display_circuit = tqcs[0] if tqcs else None

    return QKDResult(
        protocol="BBM92",
        alice_bits=alice_bits, alice_bases=alice_bases,
        bob_bits=bob_bits, bob_bases=bob_bases,
        alice_key=alice_key, bob_key=bob_key,
        circuit=display_circuit, counts=None,
    )


# --------------------------------------------------------------------------
# 3. Ekert91 - entanglement based, CHSH-style bases
# --------------------------------------------------------------------------

# Ekert91 traditionally uses 3 possible analyzer angles per side; here we
# label them symbolically. Two of Alice's angles overlap with two of Bob's,
# which is what allows key sifting; the non-overlapping combinations are
# reserved (in real E91) for a Bell/CHSH test that certifies security.
ALICE_ANGLES = {"A1": 0, "A2": np.pi / 4, "A3": np.pi / 2}
BOB_ANGLES = {"B1": np.pi / 4, "B2": np.pi / 2, "B3": 3 * np.pi / 4}
# Matching bases for key generation: A2==B1 (both pi/4) and A3==B2 (both pi/2)
MATCHING_PAIRS = {("A2", "B1"), ("A3", "B2")}


def _measure_in_angle(qc: QuantumCircuit, qubit: int, angle: float):
    """Rotate measurement basis by `angle` (about Y) before a Z-measurement."""
    qc.ry(-2 * angle, qubit)


def ekert91_protocol(n_pairs: int, backend=None, seed: Optional[int] = None) -> QKDResult:
    """
    Like BBM92 but each party randomly picks from THREE analyzer angles
    instead of two orthogonal bases. Pairs of angles that coincide between
    Alice and Bob are used for key generation (sifting); the rest could be
    used to test a CHSH/Bell inequality for eavesdropper detection (not
    computed here, but the raw correlation data is returned via `counts`).
    """
    rng = random.Random(seed)
    n = n_pairs

    alice_choices = [rng.choice(list(ALICE_ANGLES.keys())) for _ in range(n)]
    bob_choices = [rng.choice(list(BOB_ANGLES.keys())) for _ in range(n)]

    circuits = []
    for i in range(n):
        qc = QuantumCircuit(2, 2, name=f"ekert91_{i}")
        # Prepare the singlet state |Psi-> = (|01> - |10>)/sqrt(2). This is
        # the state Ekert's original 1991 protocol uses: measuring both
        # qubits along the SAME analyzer angle gives perfectly
        # ANTI-correlated results, which the sifting logic below expects.
        qc.h(0)
        qc.cx(0, 1)
        qc.x(1)
        qc.z(1)
        qc.barrier()
        _measure_in_angle(qc, 0, ALICE_ANGLES[alice_choices[i]])
        _measure_in_angle(qc, 1, BOB_ANGLES[bob_choices[i]])
        qc.measure([0, 1], [0, 1])
        circuits.append(qc)

    tqcs, memories = _run_batch(circuits, backend=backend, shots=1)
    alice_bits, bob_bits = [], []
    for m in memories:
        bitstring = m[0][::-1]
        alice_bits.append(int(bitstring[0]))
        bob_bits.append(int(bitstring[1]))

    alice_key, bob_key = [], []
    for i in range(n):
        pair = (alice_choices[i], bob_choices[i])
        if pair in MATCHING_PAIRS:
            alice_key.append(alice_bits[i])
            bob_key.append(1 - bob_bits[i])  # anti-correlated at these angles

    display_circuit = tqcs[0] if tqcs else None

    return QKDResult(
        protocol="Ekert91",
        alice_bits=alice_bits, alice_bases=alice_choices,
        bob_bits=bob_bits, bob_bases=bob_choices,
        alice_key=alice_key, bob_key=bob_key,
        circuit=display_circuit, counts=None,
    )


PROTOCOLS = {
    "BB84": bb84_protocol,
    "BBM92": bbm92_protocol,
    "Ekert91": ekert91_protocol,
}


def run_protocol(name: str, n_qubits: int, backend=None, seed: Optional[int] = None) -> QKDResult:
    if name not in PROTOCOLS:
        raise ValueError(f"Unknown protocol '{name}'. Choose from {list(PROTOCOLS)}")
    return PROTOCOLS[name](n_qubits, backend=backend, seed=seed)


if __name__ == "__main__":
    for name in PROTOCOLS:
        res = run_protocol(name, 7, seed=42)
        print(f"--- {name} ---")
        print("Alice bases:", res.alice_bases)
        print("Bob bases  :", res.bob_bases)
        print("Alice key  :", res.key_string_alice)
        print("Bob key    :", res.key_string_bob)
        print("QBER       :", res.qber)
        print()
