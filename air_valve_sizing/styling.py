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


# Pictograma de valvula de aire en estilo de linea/contorno (esquema tipo
# plano): cuerpo achaflanado con una tapa/salida lateral del mismo estilo
# (rectangulo achaflanado, a menor escala) y el tramo de tuberia debajo.
# Aprobado por el usuario tras iteracion visual. Usado como icono de los
# puntos sugeridos en el grafico.
_VALVE_ICON_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <g fill="none" stroke="{PALETTE["deep"]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round">
    <path d="M27 18 L46 18 L46 48 L20 48 L20 25 Z"/>
    <path d="M47 6 L58 6 L58 20 L43 20 L43 10 Z"/>
    <path d="M33 48 L33 60"/>
  </g>
</svg>
""".strip()

VALVE_ICON_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(_VALVE_ICON_SVG.encode("utf-8")).decode("utf-8")


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

        html, body, [class*="css"], .stMarkdown, .stButton, .stDataFrame, table {{
            font-family: 'Space Grotesk', sans-serif !important;
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
