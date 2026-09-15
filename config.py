"""
API key loading for ModelMesh.

Priority:
1. Streamlit secrets
2. Local environment variables / .env

Keys are never exposed in the UI.
"""

import os

import streamlit as st
from dotenv import load_dotenv


load_dotenv()


def get_key(name: str) -> str | None:

    try:
        value = st.secrets.get(name)

        if value:
            return str(value).strip()

    except Exception:
        pass

    value = os.environ.get(name)

    return value.strip() if value else None


def mask(key: str | None) -> str:

    return "configured" if key else "not set"