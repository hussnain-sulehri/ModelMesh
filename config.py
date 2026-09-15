"""
Key loading.

Streamlit secrets first, then the environment. Keys are never hardcoded,
never printed, and never shown in the UI.
"""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_key(name: str) -> str | None:
    try:
        value = st.secrets[name]
        if value:
            return str(value).strip()
    except Exception:
        pass

    value = os.environ.get(name)
    return value.strip() if value else None


def mask(key: str | None) -> str:
    if not key or len(key) < 8:
        return "not set"
    return "*" * (len(key) - 4) + key[-4:]