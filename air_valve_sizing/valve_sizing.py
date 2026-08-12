"""
Dimensionamiento de orificio de valvula de aire segun AWWA M51 capitulo 4,
para los tres escenarios pedidos: Purga (Tabla 4-1), Llenado (Tabla 4-2) y
Vaciado/vacio (Tabla 4-3). La seleccion de diametro replica el metodo del
manual: interpolar la capacidad de cada orificio a la presion diferencial
del punto y elegir el menor orificio nominal cuya capacidad cubra el
caudal requerido.
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from hydraulics import m3s_to_gpm, pipe_area_m2
from m51_tables import (
    TABLE_4_1,
    TABLE_4_1_DIAMETERS_IN,
    TABLE_4_2_FILLING,
    TABLE_4_3_DRAINING,
    TABLE_LARGE_ORIFICE_DIAMETERS_IN,
)

FT_S_PER_M_S = 1 / 0.3048


@dataclass
class SizingResult:
    diameter_in: float
    capacity_scfm: float
    required_scfm: float
    delta_p_psi: float
    exceeds_largest: bool
    not_applicable: bool = False
    note: str = ""


def _interp_capacity(pressures: List[float], capacities: List[float], delta_p: float) -> float:
    """Interpola la capacidad (SCFM) de una columna de orificio a una presion
    diferencial arbitraria. Por debajo del rango de la tabla se ancla en
    (0 psi, 0 SCFM); por encima, se extrapola linealmente con la ultima
    pendiente de la tabla."""
    if delta_p <= pressures[0]:
        return float(np.interp(delta_p, [0, pressures[0]], [0, capacities[0]]))
    if delta_p >= pressures[-1]:
        p1, p2 = pressures[-2], pressures[-1]
        c1, c2 = capacities[-2], capacities[-1]
        slope = (c2 - c1) / (p2 - p1)
        return max(c2 + slope * (delta_p - p2), 0.0)
    return float(np.interp(delta_p, pressures, capacities))


def select_orifice(
    table: Dict[float, List[float]], diameters: List[float], delta_p_psi: float, q_required_scfm: float
) -> SizingResult:
    pressures = sorted(table.keys())
    capacities = [
        _interp_capacity(pressures, [table[p][i] for p in pressures], delta_p_psi) for i in range(len(diameters))
    ]
    for d, cap in zip(diameters, capacities):
        if cap >= q_required_scfm:
            return SizingResult(d, cap, q_required_scfm, delta_p_psi, exceeds_largest=False)
    return SizingResult(diameters[-1], capacities[-1], q_required_scfm, delta_p_psi, exceeds_largest=True)


def purge_sizing(flow_m3s: float, dissolved_air_pct: float, delta_p_m: float) -> SizingResult:
    """Escenario de PURGA: release de aire acumulado bajo presion (Tabla 4-1).
    delta_p_m = elevacion HGL - elevacion de la valvula, en metros."""
    delta_p_psi = delta_p_m / 0.70307
    if delta_p_psi <= 0:
        return SizingResult(0.0, 0.0, 0.0, delta_p_psi, exceeds_largest=False, not_applicable=True, note="Sin presion positiva en el punto: no requiere purga")
    q_gpm = m3s_to_gpm(flow_m3s)
    q_scfm = (q_gpm / 7.48) * (dissolved_air_pct / 100.0)
    return select_orifice(TABLE_4_1, TABLE_4_1_DIAMETERS_IN, delta_p_psi, q_scfm)


def filling_sizing(diameter_m: float, fill_velocity_ms: float, delta_p_psi: float = 2.0) -> SizingResult:
    """Escenario de LLENADO (Tabla 4-2, Ec. 4-3)."""
    q_fill_m3s = pipe_area_m2(diameter_m) * fill_velocity_ms
    q_fill_gpm = m3s_to_gpm(q_fill_m3s)
    q_scfm = q_fill_gpm * 0.134 * (delta_p_psi + 14.7) / 14.7
    return select_orifice(TABLE_4_2_FILLING, TABLE_LARGE_ORIFICE_DIAMETERS_IN, delta_p_psi, q_scfm)


def draining_sizing(diameter_m: float, drain_velocity_ms: float, delta_p_psi: float = 5.0) -> SizingResult:
    """Escenario de VACIADO/DRENAJE (Tabla 4-3, misma forma de la Ec. 4-3
    aplicada a admision de aire)."""
    q_drain_m3s = pipe_area_m2(diameter_m) * drain_velocity_ms
    q_drain_gpm = m3s_to_gpm(q_drain_m3s)
    q_scfm = q_drain_gpm * 0.134 * (delta_p_psi + 14.7) / 14.7
    return select_orifice(TABLE_4_3_DRAINING, TABLE_LARGE_ORIFICE_DIAMETERS_IN, delta_p_psi, q_scfm)


def collapse_pressure_psi(wall_thickness_in: float, mean_diameter_in: float) -> float:
    """Ec. 4-4: presion de colapso de un cilindro de acero de pared delgada."""
    return 66_000_000 * (wall_thickness_in / mean_diameter_in) ** 3


def allowable_delta_p_psi(collapse_p_psi: float, safety_factor: float) -> float:
    """Ec. 4-5: presion diferencial admisible con factor de seguridad."""
    return collapse_p_psi / safety_factor
