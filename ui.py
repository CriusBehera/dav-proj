from decimal import Decimal

import pandas as pd
import streamlit as st

CREDITS = "Made by Crius Behera, Reyansh Patel | DPS Kalinga"


def card(name=None):
    return st.container(border=True, key=f"card_{name}" if name else None)


def header(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def stats(items):
    for col, (label, value) in zip(st.columns(len(items)), items):
        col.metric(label, str(value))


def to_df(rows, columns=None):
    df = pd.DataFrame(rows, columns=columns)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


def flash(message, icon="✅"):
    st.session_state.flash = (message, icon)


def show_flash():
    if "flash" in st.session_state:
        message, icon = st.session_state.pop("flash")
        st.toast(message, icon=icon)
