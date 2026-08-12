"""
Conversion de unidades y calculo hidraulico (Hazen-Williams metrico) para
construir la linea de gradiente hidraulico (HGL) a lo largo del perfil.

Todas las conversiones "a interno" usan el Sistema Internacional (m, m3/s)
como unidad canonica. Las funciones "a US" convierten a las unidades que
usan las tablas y formulas del AWWA M51 (psi, gpm, ft, in, SCFM).
"""

import math

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Conversion de carga/presion -> metros de columna de agua (mwc)
# ---------------------------------------------------------------------------
HEAD_TO_M = {
    "mwc": 1.0,
    "bar": 10.1972,
    "psi": 0.70307,
    "kg/cm2": 10.0,
}

FLOW_TO_M3S = {
    "lps": 1e-3,
    "m3/hr": 1 / 3600,
    "m3/s": 1.0,
    "gpm": 6.30902e-5,
}

LENGTH_TO_M = {
    "m": 1.0,
    "mm": 1e-3,
    "in": 0.0254,
}

M_TO_FT = 1 / 0.3048
M_TO_IN = 1 / 0.0254
M3S_TO_GPM = 1 / 6.30902e-5
M_TO_PSI = 1 / 0.70307
M_TO_BAR = 1 / 10.1972
M_TO_KGCM2 = 1 / 10.0


def head_to_m(value: float, unit: str) -> float:
    return value * HEAD_TO_M[unit]


def m_to_head(value_m: float, unit: str) -> float:
    return value_m / HEAD_TO_M[unit]


def flow_to_m3s(value: float, unit: str) -> float:
    return value * FLOW_TO_M3S[unit]


def m3s_to_flow(value_m3s: float, unit: str) -> float:
    return value_m3s / FLOW_TO_M3S[unit]


def length_to_m(value: float, unit: str) -> float:
    return value * LENGTH_TO_M[unit]


def m_to_length(value_m: float, unit: str) -> float:
    return value_m / LENGTH_TO_M[unit]


def m_to_ft(value_m: float) -> float:
    return value_m * M_TO_FT


def m_to_in(value_m: float) -> float:
    return value_m * M_TO_IN


def m3s_to_gpm(value_m3s: float) -> float:
    return value_m3s * M3S_TO_GPM


def pipe_area_m2(diameter_m: float) -> float:
    return math.pi / 4 * diameter_m**2


def hazen_williams_gradient(q_m3s: float, diameter_m: float, c_hw: float) -> float:
    """Gradiente hidraulico unitario J = hf/L (m/m), formula metrica de Hazen-Williams."""
    return 10.67 * q_m3s**1.852 / (c_hw**1.852 * diameter_m**4.87)


def build_hgl(chainage_m: np.ndarray, hgl_start_m: float, gradient_j: float) -> np.ndarray:
    """HGL(x) = HGL_inicio - J * (x - x0), para el arreglo de cadenamientos dado."""
    x0 = chainage_m[0]
    return hgl_start_m - gradient_j * (chainage_m - x0)


def elevation_at_chainage(profile_df: pd.DataFrame, chainage_m: float) -> float:
    """Interpola la elevacion del perfil completo en un cadenamiento arbitrario."""
    return float(np.interp(chainage_m, profile_df["chainage_m"], profile_df["elevation_m"]))
