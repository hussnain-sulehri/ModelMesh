"""
API key loading for ModelMesh.

Priority:
1. Streamlit Community Cloud secrets
2. Local environment variables / .env

API keys are never hardcoded or exposed in the UI.
"""

import os

import streamlit as st
from dotenv import load_dotenv


# Used for local development.
# Harmless on Streamlit Cloud if no .env file exists.
load_dotenv()


def get_key(name: str) -> str | None:
    """
    Return an API key from Streamlit secrets first,
    then fall back to environment variables.
    """

    try:
        value = st.secrets.get(name)

        if value:
            return str(value).strip()

    except Exception:
        pass

    value = os.environ.get(name)

    return value.strip() if value else None


def mask(key: str | None) -> str:
    """
    Show configuration status without revealing
    any portion of the API key.
    """

    return "configured" if key else "not set"