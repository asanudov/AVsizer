"""
Tablas del manual AWWA M51 (2016), "Air Valves: Air-Release, Air/Vacuum and
Combination", capitulo 4 "Design of Valve Orifice Size".

Los valores se transcriben tal cual aparecen impresos en el manual (unidades
imperiales: psi, SCFM, pulgadas), sin reinterpretar las formulas que las
generan (Cd=0.6, T=60F, nivel del mar). Todas las funciones de dimensionamiento
de este proyecto seleccionan el diametro de orificio interpolando/consultando
estas tablas, tal como indica el metodo de 4 pasos del propio manual
("Refer to Table X and select the orifice diameter that provides the
required capacity").
"""

# ---------------------------------------------------------------------------
# Tabla 4-1: capacidad de orificios pequenos (valvula de release de aire) en
# SCFM, Cd=0.6. Usada para el escenario de PURGA (liberacion de aire bajo
# presion durante operacion normal).
# ---------------------------------------------------------------------------
TABLE_4_1_DIAMETERS_IN = [1 / 16, 3 / 32, 1 / 8, 3 / 16, 1 / 4, 5 / 16, 3 / 8, 7 / 16, 1 / 2, 1.0]

TABLE_4_1 = {
    25: [1.3, 3.0, 5.4, 12.1, 21.5, 33.7, 48.5, 66.0, 86.2, 344.7],
    50: [2.2, 4.9, 8.8, 19.8, 35.1, 54.9, 79.0, 107.5, 140.5, 561.8],
    75: [3.0, 6.8, 12.2, 27.4, 48.7, 76.1, 109.5, 149.1, 194.7, 779.0],
    100: [3.9, 8.8, 15.6, 35.0, 62.2, 97.3, 140.1, 190.6, 249.0, 996.0],
    125: [4.7, 10.7, 19.0, 42.6, 75.8, 118.5, 170.6, 232.2, 303.3, 1213.0],
    150: [5.6, 12.6, 22.3, 50.3, 89.4, 139.7, 201.1, 273.7, 357.5, 1430.0],
    175: [6.4, 14.5, 25.7, 57.9, 103.0, 160.9, 231.6, 315.3, 411.8, 1647.0],
    200: [7.3, 16.4, 29.1, 65.5, 116.5, 182.1, 262.2, 356.8, 466.1, 1864.0],
    225: [8.1, 18.3, 32.5, 73.2, 130.1, 203.3, 292.7, 398.4, 520.3, 2081.0],
    250: [9.0, 20.2, 35.9, 80.8, 143.7, 224.5, 323.2, 439.9, 574.6, 2298.0],
    275: [9.8, 22.1, 39.3, 88.4, 157.2, 245.7, 353.8, 481.5, 628.9, 2515.0],
    300: [10.7, 24.0, 42.7, 96.1, 170.8, 266.9, 384.3, 523.0, 683.2, 2732.0],
}

# ---------------------------------------------------------------------------
# Tabla 4-2: descarga de orificios grandes (SCFM) al VENTEAR aire durante el
# LLENADO de la linea. Cd=0.6, T=60F, nivel del mar.
# ---------------------------------------------------------------------------
TABLE_LARGE_ORIFICE_DIAMETERS_IN = [1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20]

TABLE_4_2_FILLING = {
    1.0: [68, 271, 611, 1086, 2443, 4343, 6786, 9772, 13300, 17372, 21986, 27143],
    1.5: [83, 330, 743, 1321, 2973, 5285, 8257, 11891, 16185, 21139, 26754, 33030],
    2.0: [95, 379, 853, 1516, 3411, 6064, 9475, 13644, 18571, 24255, 30698, 37899],
    2.5: [105, 421, 946, 1683, 3786, 6731, 10517, 15144, 20612, 26922, 34074, 42066],
    3.0: [114, 457, 1028, 1828, 4114, 7313, 11427, 16454, 22396, 29252, 37022, 45706],
    3.5: [122, 489, 1099, 1955, 4398, 7818, 12216, 17591, 23944, 31273, 39581, 48865],
    4.0: [129, 517, 1164, 2069, 4655, 8275, 12929, 18618, 25341, 33099, 41891, 51717],
    4.5: [136, 543, 1221, 2170, 4883, 8681, 13564, 19532, 26586, 34724, 43948, 54256],
    5.0: [141, 565, 1272, 2261, 5086, 9042, 14129, 20345, 27692, 36169, 45777, 56515],
}

# ---------------------------------------------------------------------------
# Tabla 4-3: ingreso (inflow) de aire por orificios grandes (SCFM) al ADMITIR
# aire durante VACIADO/condiciones de vacio (flujo por gravedad). Cd=0.6.
# ---------------------------------------------------------------------------
TABLE_4_3_DRAINING = {
    1.0: [66, 264, 593, 1055, 2374, 4220, 6593, 9495, 12923, 16879, 21363, 26374],
    1.5: [79, 317, 713, 1268, 2853, 5072, 7925, 11411, 15532, 20287, 25676, 31698],
    2.0: [90, 359, 808, 1436, 3231, 5745, 8976, 12926, 17594, 22980, 29083, 35905],
    2.5: [98, 394, 886, 1575, 3543, 6298, 9841, 14171, 19289, 25194, 31886, 39365],
    3.0: [106, 423, 951, 1691, 3804, 6763, 10567, 15217, 20712, 27052, 34238, 42269],
    3.5: [112, 447, 1007, 1789, 4026, 7158, 11184, 16104, 21920, 28630, 36235, 44735],
    4.0: [117, 468, 1054, 1874, 4215, 7494, 11710, 16862, 22951, 29977, 37939, 46838],
    4.5: [122, 486, 1094, 1945, 4377, 7782, 12159, 17509, 23831, 31126, 39394, 48635],
    5.0: [125, 502, 1129, 2007, 4515, 8026, 12541, 18059, 24581, 32105, 40633, 50165],
}

# ---------------------------------------------------------------------------
# Tabla 4-4: areas nominales de orificio (in2) para valvula unica o en
# cluster. Se incluye como referencia; el MVP de esta app no arma clusters,
# solo selecciona valvulas individuales.
# ---------------------------------------------------------------------------
TABLE_4_4_AREAS = {
    "single": [0.79, 3.14, 7.1, 12.6, 28.3, 50, 79, 113, 154, 201, 254, 314],
    "two_valve_cluster": [1.57, 6.28, 14.1, 25.1, 56.5, 101, 157, 226, 308, 402, 509, 628],
    "three_valve_cluster": [2.36, 9.42, 21.2, 37.7, 84.8, 151, 236, 339, 462, 603, 763, 942],
}

# Coeficientes de Hazen-Williams (C) de diseno estandar por material.
# Distintos del coeficiente de Chezy que usa el M51 en su Ec. 4-6 (no usado
# en este proyecto, ver README / plan).
HAZEN_WILLIAMS_C = {
    "PEAD (HDPE)": 150,
    "PVC": 150,
    "HD (Hierro Ductil)": 130,
    "Acero": 120,
}

# Porcentajes de aire disuelto disponibles para el dimensionamiento de purga
# (M51 pag. 24: 2% es la base habitual; 2-5% se sugiere para aguas con gases).
DISSOLVED_AIR_PERCENT_OPTIONS = [0.2, 0.5, 0.7, 1.0, 2.0]
DISSOLVED_AIR_PERCENT_DEFAULT = 2.0

# Coeficiente de rugosidad de Manning por material, usado para estimar el
# caudal de flujo por gravedad (M51 pag. 28-32, "Sizing for Gravity Flow")
# en las crestas adyacentes a un desfogue. Es un coeficiente DISTINTO del de
# Hazen-Williams (arriba): la Ec. 4-6 del M51 (Q=0.0472*C*S*ID^5, con C tipo
# Chezy) no pudo verificarse de forma confiable a partir del texto extraido
# del PDF (el resultado no reproducia el ejemplo numerico del propio manual),
# por lo que se usa en su lugar la formula de Manning para tuberia llena
# -explicitamente autorizada por el M51 como alternativa a la Fig. 4-1/Ec 4-6-
# validada contra el ejemplo del manual (Estacion 10+00, S=0.04, D=24 in):
# con n=0.012 arroja ~2,942 SCFM vs. los 3,000 SCFM del manual (~2% de error).
MANNING_N_BY_MATERIAL = {
    "PEAD (HDPE)": 0.009,
    "PVC": 0.009,
    "HD (Hierro Ductil)": 0.012,
    "Acero": 0.012,
}
