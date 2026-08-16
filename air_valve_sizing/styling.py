"""Tipografia Space Grotesk (embebida en base64) y paleta de colores 'agua'."""

import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).parent / "assets"

# Paleta "agua": azul profundo -> cian, para fondos, acentos y trazas de grafico.
PALETTE = {
    "deep": "#0B3D91",
    "primary": "#0EA5E9",
    "light": "#7DD3FC",
    "pale": "#E0F2FE",
    "foam": "#F0FAFF",
    "ink": "#0B2942",
    "warn": "#F59E0B",
    "alert": "#EF4444",
    "ok": "#10B981",
}


@st.cache_data(show_spinner=False)
def _font_base64(filename: str) -> str:
    return base64.b64encode((ASSETS_DIR / filename).read_bytes()).decode("utf-8")


def inject_theme() -> None:
    medium_b64 = _font_base64("SpaceGrotesk-Medium.ttf")
    bold_b64 = _font_base64("SpaceGrotesk-Bold.ttf")

    st.markdown(
        f"""
        <style>
        @font-face {{
            font-family: 'Space Grotesk';
            src: url(data:font/ttf;base64,{medium_b64}) format('truetype');
            font-weight: 400 500;
            font-style: normal;
        }}
        @font-face {{
            font-family: 'Space Grotesk';
            src: url(data:font/ttf;base64,{bold_b64}) format('truetype');
            font-weight: 600 700;
            font-style: normal;
        }}

        html, body, [class*="css"], .stMarkdown, .stButton, .stDataFrame, table,
        p, span, div, label, li, a, button, input, textarea, select {{
            font-family: 'Space Grotesk', sans-serif !important;
        }}

        /* Los iconos de Streamlit (flechas de expander, ayuda "?", etc.) usan una
           fuente de iconos por ligatura de texto: deben quedar excluidos de la
           regla anterior o se veria el nombre del icono en vez del glifo. */
        [data-testid="stIconMaterial"] {{
            font-family: 'Material Symbols Rounded' !important;
        }}

        h1, h2, h3, h4 {{
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 700 !important;
            color: {PALETTE["deep"]} !important;
        }}

        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(180deg, {PALETTE["foam"]} 0%, #FFFFFF 320px);
        }}

        section[data-testid="stSidebar"] {{
            background-color: {PALETTE["pale"]};
            border-right: 1px solid {PALETTE["light"]};
        }}

        div.stButton > button, div.stDownloadButton > button, div.stFormSubmitButton > button {{
            background-color: {PALETTE["primary"]} !important;
            color: white !important;
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover, div.stFormSubmitButton > button:hover {{
            background-color: {PALETTE["deep"]} !important;
            color: white !important;
        }}

        [data-testid="stMetricValue"] {{
            color: {PALETTE["deep"]};
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
        }}
        .stTabs [aria-selected="true"] {{
            color: {PALETTE["deep"]} !important;
            border-bottom-color: {PALETTE["primary"]} !important;
        }}

        .wv-banner {{
            background-color: {PALETTE["pale"]};
            border: 1px solid {PALETTE["light"]};
            border-radius: 10px;
            padding: 10px 14px;
            font-size: 14px;
            color: {PALETTE["ink"]};
            margin-bottom: 10px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
