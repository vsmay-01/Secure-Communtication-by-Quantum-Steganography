"""
app.py
-------
Interactive Streamlit UI for Quantum Steganography — mirrors the flow of
the reference project:

    1. Slider to choose the number of qubits.
    2. Enter a secret message -> view a generated quantum circuit.
    3. View the randomly generated QKD key + bases for Alice & Bob.
    4. Enter a carrier/cover sentence -> click Encrypt to see the stego text.
    5. Click Decode to recover the original secret message.
    6. A "Compare simulators" tab shows ideal vs. noisy-backend results.

Run with:
    streamlit run app.py
"""

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from qiskit.visualization import circuit_drawer

from qkd_protocols import run_protocol, PROTOCOLS
from steganography import encode, decode, capacity, encrypt_message, text_to_bits
from noisy_backend import get_ideal_backend, build_noisy_backend

st.set_page_config(page_title="Quantum Steganography", layout="wide")

st.title("🔐 Quantum Steganography")
st.caption(
    "Hide a secret message inside an ordinary sentence, protected by a key "
    "generated with real Quantum Key Distribution (QKD) protocols — "
    "BB84, BBM92, and Ekert91 — simulated with Qiskit."
)

tab_demo, tab_compare = st.tabs(["🕹️ Interactive Demo", "📊 Compare Simulators"])

# ---------------------------------------------------------------------
# TAB 1: Interactive demo
# ---------------------------------------------------------------------
with tab_demo:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. Choose a QKD protocol")
        protocol_name = st.radio(
            "Protocol", list(PROTOCOLS.keys()), horizontal=True,
            help="BB84: prepare & measure. BBM92 / Ekert91: entanglement-based.",
        )

        st.subheader("2. Set the number of qubits")
        n_qubits = st.slider(
            "Number of qubits / entangled pairs",
            min_value=1, max_value=64, value=7,
            help="7 is a good default — enough bits usually survive sifting "
                 "to encode a short secret message.",
        )

        st.subheader("3. Enter the secret message")
        secret_message = st.text_input(
            "Secret message (small letters recommended)", value="bnmit",
        )

        if st.button("🔑 Generate QKD key", type="primary"):
            with st.spinner(f"Running {protocol_name} on {n_qubits} qubits..."):
                result = run_protocol(protocol_name, n_qubits, seed=None)
            st.session_state["qkd_result"] = result
            st.session_state["secret_message"] = secret_message

        result = st.session_state.get("qkd_result")

        if result is not None:
            st.markdown("**Alice's bases:** " + " ".join(result.alice_bases))
            st.markdown("**Bob's bases:** " + " ".join(result.bob_bases))
            c1, c2, c3 = st.columns(3)
            c1.metric("Alice key", result.key_string_alice or "—")
            c2.metric("Bob key", result.key_string_bob or "—")
            c3.metric("QBER", f"{result.qber:.2f}")

            if result.circuit is not None:
                st.markdown("Example single-pair/qubit circuit used:")
                fig = circuit_drawer(result.circuit, output="mpl", style={"name": "iqp"})
                st.pyplot(fig, clear_figure=True)

    with col_right:
        st.subheader("4. Enter the carrier / cover sentence")
        cover_text = st.text_area(
            "Carrier message",
            value="Bangalore is known as the silicon city of india",
            height=80,
        )

        result = st.session_state.get("qkd_result")
        secret_message = st.session_state.get("secret_message", secret_message)

        if result is not None and result.alice_key:
            needed_bits = len(secret_message.encode("utf-8")) * 8
            cap = capacity(cover_text)
            st.caption(f"Cover sentence capacity: {cap} bits | secret needs: {needed_bits} bits")

            colA, colB = st.columns(2)
            with colA:
                if st.button("🔒 Encrypt", use_container_width=True):
                    if cap < needed_bits:
                        st.error(
                            f"Cover sentence too short — needs at least "
                            f"{needed_bits} letters, has {cap}. Try a longer sentence."
                        )
                    else:
                        stego = encode(cover_text, secret_message, result.alice_key)
                        st.session_state["stego_text"] = stego

            stego_text = st.session_state.get("stego_text")
            if stego_text:
                st.text_area("Encoded (stego) message", value=stego_text, height=80)

            with colB:
                if st.button("🔓 Decode", use_container_width=True):
                    if not stego_text:
                        st.warning("Encrypt a message first.")
                    else:
                        recovered = decode(stego_text, len(secret_message), result.bob_key)
                        st.session_state["recovered"] = recovered

            recovered = st.session_state.get("recovered")
            if recovered:
                st.success(f"Decoded message: **{recovered}**")
                if recovered == secret_message:
                    st.caption("✅ Matches the original secret message exactly.")
                else:
                    st.caption("⚠️ Doesn't match — likely due to simulated quantum noise "
                               "(see QBER) or a very short sifted key. Try more qubits.")
        else:
            st.info("Generate a QKD key on the left first.")

# ---------------------------------------------------------------------
# TAB 2: Compare simulators
# ---------------------------------------------------------------------
with tab_compare:
    st.subheader("Ideal simulator vs. noisy ('FakeWashingtonV2'-style) backend")
    st.write(
        "Real quantum computers are noisy. This compares the sifted-key "
        "agreement between Alice and Bob on a perfect simulator versus a "
        "simulator with a realistic gate/readout noise model."
    )
    n_compare = st.slider("Qubits/pairs for comparison", 8, 64, 24, key="compare_slider")

    if st.button("Run comparison"):
        ideal_backend = get_ideal_backend()
        noisy_backend = build_noisy_backend()
        rows = []
        for name in PROTOCOLS:
            n = n_compare if name == "BB84" else max(8, n_compare // 2)
            ideal_r = run_protocol(name, n, backend=ideal_backend, seed=3)
            noisy_r = run_protocol(name, n, backend=noisy_backend, seed=3)
            rows.append((name, ideal_r.qber, noisy_r.qber, len(ideal_r.alice_key)))

        fig, ax = plt.subplots(figsize=(6, 3.5))
        names = [r[0] for r in rows]
        ideal_q = [r[1] for r in rows]
        noisy_q = [r[2] for r in rows]
        import numpy as np
        x = np.arange(len(names))
        width = 0.35
        ax.bar(x - width / 2, ideal_q, width, label="Ideal simulator", color="#5b8fe0")
        ax.bar(x + width / 2, noisy_q, width, label="Noisy backend", color="#e0417c")
        ax.set_xticks(x)
        ax.set_xticklabels(names)
        ax.set_ylabel("QBER")
        ax.legend()
        ax.set_title("Quantum Bit Error Rate: ideal vs noisy")
        st.pyplot(fig, clear_figure=True)

        st.table(
            {
                "Protocol": names,
                "Ideal QBER": [f"{v:.2f}" for v in ideal_q],
                "Noisy QBER": [f"{v:.2f}" for v in noisy_q],
                "Sifted key length": [r[3] for r in rows],
            }
        )
