"""
noisy_backend.py
------------------
Provides a noisy simulator backend to stand in for the reference project's
`FakeWashingtonV2()` (a fake/mock backend that mimics a real IBM quantum
computer's noise profile). Rather than depending on the heavy
`qiskit-ibm-runtime` fake-provider package, we build an equivalent noise
model by hand with Qiskit Aer's `NoiseModel`, using realistic-ish
depolarizing + readout error rates. This keeps the project lightweight
while still demonstrating the *effect* that real hardware noise has on
QKD key agreement and steganographic decoding.

If `qiskit_ibm_runtime` IS installed in your environment, you can swap in
the real `FakeWashingtonV2` backend instead — see `get_real_fake_backend()`.
"""

from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

# Large enough qubit count to comfortably fit demo circuits (BBM92/Ekert91
# use 2 qubits per pair, so up to ~32 key-bits worth of entangled pairs).
MAX_QUBITS = 64


def build_noisy_backend(
    single_qubit_error: float = 0.01,
    two_qubit_error: float = 0.03,
    readout_error: float = 0.02,
    n_qubits: int = MAX_QUBITS,
) -> AerSimulator:
    """
    Build an AerSimulator with a hand-crafted noise model approximating a
    real superconducting quantum processor (gate errors + readout errors).
    Uses a fully-connected coupling map sized to `n_qubits` so demo
    circuits of reasonable size always fit (a real device would instead
    have a sparse, hardware-specific coupling map).
    """
    noise_model = NoiseModel()

    # Depolarizing error on single-qubit gates
    error_1q = depolarizing_error(single_qubit_error, 1)
    noise_model.add_all_qubit_quantum_error(error_1q, ["h", "x", "ry", "rz", "sx", "id"])

    # Depolarizing error on two-qubit gates
    error_2q = depolarizing_error(two_qubit_error, 2)
    noise_model.add_all_qubit_quantum_error(error_2q, ["cx"])

    # Readout error
    ro_error = ReadoutError([[1 - readout_error, readout_error],
                              [readout_error, 1 - readout_error]])
    noise_model.add_all_qubit_readout_error(ro_error)

    # No coupling_map is set: for this educational simulation we care about
    # *gate-error and readout-error rates*, not a specific chip's physical
    # qubit layout, so any-to-any connectivity is assumed.
    return AerSimulator(noise_model=noise_model, basis_gates=noise_model.basis_gates)


def get_ideal_backend() -> AerSimulator:
    """The noise-free reference simulator (equivalent to `qasm_simulator`)."""
    return AerSimulator()


def get_real_fake_backend():
    """
    Optional: use IBM's real FakeWashingtonV2 mock backend if
    qiskit-ibm-runtime is installed. Falls back to the hand-built noisy
    backend above if it isn't available.
    """
    try:
        from qiskit_ibm_runtime.fake_provider import FakeWashingtonV2
        return FakeWashingtonV2()
    except ImportError:
        return build_noisy_backend()


if __name__ == "__main__":
    from qkd_protocols import run_protocol

    ideal = get_ideal_backend()
    noisy = build_noisy_backend()

    # BB84 uses 1 qubit per key-bit; BBM92/Ekert91 use 2 (entangled pairs),
    # and Ekert91's arbitrary-angle rotations aren't Clifford, so it needs
    # the (memory-hungry) statevector method -> keep sizes modest here.
    sizes = {"BB84": 20, "BBM92": 16, "Ekert91": 12}
    for name in ["BB84", "BBM92", "Ekert91"]:
        n = sizes[name]
        r_ideal = run_protocol(name, n, backend=ideal, seed=1)
        r_noisy = run_protocol(name, n, backend=noisy, seed=1)
        print(f"{name}: ideal QBER={r_ideal.qber:.3f}  noisy QBER={r_noisy.qber:.3f}")
