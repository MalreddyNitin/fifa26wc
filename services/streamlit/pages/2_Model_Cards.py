from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
st.title("Model cards")
cards = sorted((ROOT / "docs/model_cards").glob("*.md"))
for card in cards:
    st.markdown(card.read_text(encoding="utf-8"))
