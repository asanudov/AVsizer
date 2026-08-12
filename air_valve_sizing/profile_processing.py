"""
Procesamiento del perfil de la conduccion: limpieza del CSV, simplificacion
(Ramer-Douglas-Peucker) para perfiles con demasiados nodos, y localizacion
de valvulas de aire segun las reglas del capitulo 3 del AWWA M51 (Fig. 3-1):
quiebres de pendiente, puntos altos/bajos, tramos horizontales largos,
ascensos/descensos largos (cada 400-800 m) y puntos altos adyacentes a
desfogues/drenajes declarados por el usuario.

La simplificacion RDP se usa SOLO para decidir donde hay quiebres de
pendiente relevantes; la elevacion de cada valvula sugerida siempre se
interpola desde el perfil COMPLETO para no perder precision.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

HORIZONTAL_EPS = 0.001  # m/m (~0.1%)-> por debajo de esto se considera "horizontal"

# Prioridad para desempate al fusionar puntos muy cercanos (mayor = mas importante)
CATEGORY_PRIORITY = {
    "descarga_bombeo": 100,
    "punto_alto": 90,
    "fin_tramo_horizontal": 80,
    "inicio_tramo_horizontal": 80,
    "aumento_pendiente_bajada": 70,
    "disminucion_pendiente_subida": 70,
    "extremo_linea": 60,
    "periodico_ascenso": 40,
    "periodico_horizontal": 40,
    "periodico_descenso": 40,
}


def load_profile(raw_df: pd.DataFrame, chainage_col: str, elevation_col: str) -> pd.DataFrame:
    df = raw_df[[chainage_col, elevation_col]].copy()
    df.columns = ["chainage_m", "elevation_m"]
    df["chainage_m"] = pd.to_numeric(df["chainage_m"], errors="coerce")
    df["elevation_m"] = pd.to_numeric(df["elevation_m"], errors="coerce")
    df = df.dropna().sort_values("chainage_m").drop_duplicates(subset="chainage_m", keep="first")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Simplificacion (Ramer-Douglas-Peucker adaptado a perfil x->y de una via)
# ---------------------------------------------------------------------------
def _rdp_keep_indices(x: np.ndarray, y: np.ndarray, tolerance: float) -> List[int]:
    n = len(x)
    if n < 3:
        return list(range(n))
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        x0, y0, x1, y1 = x[start], y[start], x[end], y[end]
        if x1 == x0:
            continue
        seg_x = x[start + 1 : end]
        seg_y = y[start + 1 : end]
        y_line = y0 + (y1 - y0) * (seg_x - x0) / (x1 - x0)
        dev = np.abs(seg_y - y_line)
        idx_max = int(np.argmax(dev))
        max_dev = dev[idx_max]
        if max_dev > tolerance:
            real_idx = start + 1 + idx_max
            keep[real_idx] = True
            stack.append((start, real_idx))
            stack.append((real_idx, end))
    return np.nonzero(keep)[0].tolist()


DEFAULT_SLOPE_TOLERANCE_M = 0.5  # filtra ruido/redondeo tipico de topografia (p.ej. cotas a metro entero)
DEFAULT_TARGET_VERTICES_PER_KM = 12.0  # densidad objetivo de vertices tras simplificar, independiente del muestreo del CSV
MIN_TARGET_VERTICES = 15
MAX_TARGET_VERTICES = 250


def simplify_profile(
    df: pd.DataFrame,
    base_tolerance_m: float = DEFAULT_SLOPE_TOLERANCE_M,
    target_vertices_per_km: float = DEFAULT_TARGET_VERTICES_PER_KM,
) -> "tuple[pd.DataFrame, bool]":
    """Simplifica el perfil con RDP para filtrar ruido/redondeo de la
    topografia (quiebres de pendiente espurios) y quedarse solo con quiebres
    de pendiente realmente significativos, sin importar cuantos puntos ni
    que tan seguido esten muestreados en el CSV original.

    Primero se aplica una pasada base con base_tolerance_m (tolerancia
    minima). La densidad de vertices resultante se limita ademas segun la
    longitud de la linea (target_vertices_per_km): si el perfil es denso o
    "ruidoso" y aun asi quedan demasiados vertices para esa longitud, se
    sube la tolerancia adaptativamente (busqueda binaria) hasta acercarse al
    objetivo. Devuelve (perfil_para_clasificar, se_redujo_el_numero_de_puntos).
    """
    if len(df) < 3:
        return df.reset_index(drop=True), False

    x = df["chainage_m"].to_numpy()
    y = df["elevation_m"].to_numpy()

    line_length_km = max((x[-1] - x[0]) / 1000.0, 0.001)
    target_hi = int(np.clip(round(line_length_km * target_vertices_per_km), MIN_TARGET_VERTICES, MAX_TARGET_VERTICES))
    target_hi = min(target_hi, len(df))
    target_lo = max(5, target_hi // 2)

    idx = _rdp_keep_indices(x, y, base_tolerance_m)

    if len(idx) > target_hi:
        elev_range = max(float(y.max() - y.min()), 1.0)
        tol_lo, tol_hi = base_tolerance_m, elev_range
        for _ in range(40):
            tol_mid = (tol_lo + tol_hi) / 2
            idx = _rdp_keep_indices(x, y, tol_mid)
            n = len(idx)
            if target_lo <= n <= target_hi:
                break
            if n > target_hi:
                tol_lo = tol_mid
            else:
                tol_hi = tol_mid

    simplified = df.iloc[idx].reset_index(drop=True)
    return simplified, len(simplified) < len(df)


# ---------------------------------------------------------------------------
# Clasificacion de quiebres de pendiente (Fig. 3-1 del M51)
# ---------------------------------------------------------------------------
def _sign(slope: float, eps: float) -> int:
    if slope > eps:
        return 1
    if slope < -eps:
        return -1
    return 0


def _classify_pair(s_before: float, s_after: float, eps: float):
    """Devuelve (categoria, tipo_de_valvula, es_obligatoria) o (None, None, False)."""
    sb, sa = _sign(s_before, eps), _sign(s_after, eps)

    if sb == 0 and sa == 0:
        return None, None, False
    if sb == 0:
        return "fin_tramo_horizontal", "Combinacion", True
    if sa == 0:
        return "inicio_tramo_horizontal", "Combinacion", True
    if sb > 0 and sa < 0:
        return "punto_alto", "Combinacion", True
    if sb < 0 and sa > 0:
        return "punto_bajo", None, False
    if sb < 0 and sa < 0:
        if s_after < s_before:
            return "aumento_pendiente_bajada", "Combinacion", True
        return "disminucion_pendiente_bajada", None, False
    if sb > 0 and sa > 0:
        if s_after > s_before:
            return "aumento_pendiente_subida", None, False
        return "disminucion_pendiente_subida", "Aire/Vacio o Combinacion", True
    return None, None, False


def classify_breakpoints(simplified_df: pd.DataFrame, eps: float = HORIZONTAL_EPS) -> List[dict]:
    x = simplified_df["chainage_m"].to_numpy()
    y = simplified_df["elevation_m"].to_numpy()
    if len(x) < 3:
        return []
    slopes = np.diff(y) / np.diff(x)
    results = []
    for i in range(1, len(x) - 1):
        cat, vtype, mandatory = _classify_pair(slopes[i - 1], slopes[i], eps)
        if cat is not None and mandatory:
            results.append(
                {
                    "chainage_m": float(x[i]),
                    "elevation_m": float(y[i]),
                    "category": cat,
                    "valve_type": vtype,
                    "source": "quiebre_pendiente",
                }
            )
    return results


# ---------------------------------------------------------------------------
# Insercion de valvulas periodicas a lo largo de tramos largos
# ---------------------------------------------------------------------------
def insert_periodic_valves(
    full_df: pd.DataFrame, boundary_chainages: List[float], spacing_m: float, eps: float = HORIZONTAL_EPS
) -> List[dict]:
    boundaries = sorted(set(boundary_chainages))
    periodic = []
    for c0, c1 in zip(boundaries[:-1], boundaries[1:]):
        run_length = c1 - c0
        if run_length <= spacing_m:
            continue
        e0 = float(np.interp(c0, full_df["chainage_m"], full_df["elevation_m"]))
        e1 = float(np.interp(c1, full_df["chainage_m"], full_df["elevation_m"]))
        run_slope = (e1 - e0) / run_length if run_length else 0.0
        if abs(run_slope) < eps:
            category, vtype = "periodico_horizontal", "Aire-Release o Combinacion"
        elif run_slope > 0:
            category, vtype = "periodico_ascenso", "Aire/Vacio o Combinacion"
        else:
            category, vtype = "periodico_descenso", "Aire-Release o Combinacion"

        n_intervals = int(run_length // spacing_m)
        for k in range(1, n_intervals + 1):
            c = c0 + k * spacing_m
            if c >= c1 - spacing_m / 2:
                break
            e = float(np.interp(c, full_df["chainage_m"], full_df["elevation_m"]))
            periodic.append(
                {"chainage_m": c, "elevation_m": e, "category": category, "valve_type": vtype, "source": "periodico"}
            )
    return periodic


# ---------------------------------------------------------------------------
# Puntos altos adyacentes a desfogues/drenajes declarados por el usuario
# ---------------------------------------------------------------------------
def assign_drain_crests(candidates: List[dict], full_df: pd.DataFrame, drain_chainages: List[float]) -> List[dict]:
    if not drain_chainages:
        return candidates

    x_start, x_end = float(full_df["chainage_m"].iloc[0]), float(full_df["chainage_m"].iloc[-1])
    high_points = sorted([c for c in candidates if c["category"] == "punto_alto"], key=lambda c: c["chainage_m"])
    mandatory_points = sorted(candidates, key=lambda c: c["chainage_m"])

    def _nearest_before(chainage, pool):
        cands = [c for c in pool if c["chainage_m"] < chainage]
        return max(cands, key=lambda c: c["chainage_m"]) if cands else None

    def _nearest_after(chainage, pool):
        cands = [c for c in pool if c["chainage_m"] > chainage]
        return min(cands, key=lambda c: c["chainage_m"]) if cands else None

    for drain_c in drain_chainages:
        before = _nearest_before(drain_c, high_points) or _nearest_before(drain_c, mandatory_points)
        after = _nearest_after(drain_c, high_points) or _nearest_after(drain_c, mandatory_points)

        if before is None:
            e = float(np.interp(x_start, full_df["chainage_m"], full_df["elevation_m"]))
            before = {"chainage_m": x_start, "elevation_m": e, "category": "extremo_linea", "valve_type": "Combinacion", "source": "cresta_desfogue"}
            candidates.append(before)
            mandatory_points.append(before)
        if after is None:
            e = float(np.interp(x_end, full_df["chainage_m"], full_df["elevation_m"]))
            after = {"chainage_m": x_end, "elevation_m": e, "category": "extremo_linea", "valve_type": "Combinacion", "source": "cresta_desfogue"}
            candidates.append(after)
            mandatory_points.append(after)

        for point in (before, after):
            point["needs_drain_sizing"] = True
            point.setdefault("drain_refs", [])
            point["drain_refs"].append(drain_c)

    return candidates


# ---------------------------------------------------------------------------
# Fusion de puntos demasiado cercanos entre si
# ---------------------------------------------------------------------------
def merge_close_points(candidates: List[dict], min_spacing_m: float) -> List[dict]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda c: c["chainage_m"])
    merged: List[dict] = [ordered[0]]
    for point in ordered[1:]:
        last = merged[-1]
        if point["chainage_m"] - last["chainage_m"] < min_spacing_m:
            keep, drop = (last, point)
            if CATEGORY_PRIORITY.get(point["category"], 0) > CATEGORY_PRIORITY.get(last["category"], 0):
                keep, drop = point, last
            if drop.get("needs_drain_sizing"):
                keep["needs_drain_sizing"] = True
                keep.setdefault("drain_refs", [])
                keep["drain_refs"].extend(drop.get("drain_refs", []))
            merged[-1] = keep
        else:
            merged.append(point)
    return merged


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------
def build_valve_locations(
    full_df: pd.DataFrame,
    is_impulsion: bool,
    drain_chainages: Optional[List[float]] = None,
    spacing_m: float = 500.0,
    min_spacing_m: float = 50.0,
    slope_tolerance_m: float = DEFAULT_SLOPE_TOLERANCE_M,
    target_vertices_per_km: float = DEFAULT_TARGET_VERTICES_PER_KM,
) -> "tuple[pd.DataFrame, bool]":
    drain_chainages = drain_chainages or []
    simplified_df, was_simplified = simplify_profile(
        full_df, base_tolerance_m=slope_tolerance_m, target_vertices_per_km=target_vertices_per_km
    )

    candidates = classify_breakpoints(simplified_df)

    x_start = float(full_df["chainage_m"].iloc[0])
    x_end = float(full_df["chainage_m"].iloc[-1])
    e_start = float(full_df["elevation_m"].iloc[0])

    if is_impulsion:
        candidates.append(
            {
                "chainage_m": x_start,
                "elevation_m": e_start,
                "category": "descarga_bombeo",
                "valve_type": "Aire/Vacio o Combinacion",
                "source": "descarga_bombeo",
            }
        )

    boundary_chainages = [x_start, x_end] + [c["chainage_m"] for c in candidates]
    candidates.extend(insert_periodic_valves(full_df, boundary_chainages, spacing_m))

    candidates = assign_drain_crests(candidates, full_df, drain_chainages)
    candidates = merge_close_points(candidates, min_spacing_m)
    candidates.sort(key=lambda c: c["chainage_m"])

    result_df = pd.DataFrame(candidates)
    if result_df.empty:
        result_df = pd.DataFrame(columns=["chainage_m", "elevation_m", "category", "valve_type", "source", "needs_drain_sizing", "drain_refs"])
    else:
        if "needs_drain_sizing" not in result_df.columns:
            result_df["needs_drain_sizing"] = False
        result_df["needs_drain_sizing"] = result_df["needs_drain_sizing"].fillna(False)
        if "drain_refs" not in result_df.columns:
            result_df["drain_refs"] = [[] for _ in range(len(result_df))]
        result_df["drain_refs"] = result_df["drain_refs"].apply(lambda v: v if isinstance(v, list) else [])

    return result_df.reset_index(drop=True), was_simplified
