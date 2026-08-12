import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import hydraulics as hyd
import profile_processing as pp
import valve_sizing as vs
from m51_tables import DISSOLVED_AIR_PERCENT_DEFAULT, DISSOLVED_AIR_PERCENT_OPTIONS, HAZEN_WILLIAMS_C
from styling import PALETTE, inject_theme

st.set_page_config(page_title="Dimensionamiento de Válvulas de Aire — AWWA M51", layout="wide", page_icon="💧")
inject_theme()

HEAD_UNITS = ["mwc", "bar", "psi", "kg/cm2"]
FLOW_UNITS = ["lps", "m3/hr", "m3/s", "gpm"]
LENGTH_UNITS = ["m", "mm", "in"]

CATEGORY_LABELS = {
    "punto_alto": "Punto alto",
    "fin_tramo_horizontal": "Fin de tramo horizontal",
    "inicio_tramo_horizontal": "Inicio de tramo horizontal",
    "aumento_pendiente_bajada": "Aumento de pendiente en bajada",
    "disminucion_pendiente_subida": "Disminución de pendiente en subida",
    "descarga_bombeo": "Descarga de bombeo",
    "extremo_linea": "Extremo de línea (adyacente a desfogue)",
    "periodico_ascenso": "Punto periódico — ascenso largo",
    "periodico_horizontal": "Punto periódico — tramo horizontal",
    "periodico_descenso": "Punto periódico — descenso largo",
}

MARKER_COLOR_BY_SOURCE = {
    "quiebre_pendiente": PALETTE["deep"],
    "descarga_bombeo": PALETTE["ok"],
    "cresta_desfogue": PALETTE["warn"],
    "periodico": PALETTE["light"],
}


def number_with_unit(label, default_value, units, default_unit, key, help_text=None, min_value=0.0):
    col1, col2 = st.columns([3, 1])
    value = col1.number_input(label, min_value=min_value, value=default_value, key=f"{key}_val", help=help_text)
    unit = col2.selectbox("unidad", units, index=units.index(default_unit), key=f"{key}_unit", label_visibility="visible")
    return value, unit


st.title("Dimensionamiento y localización de válvulas de aire — AWWA M51")
st.caption(
    "Calcula ubicación (cadenamiento y elevación) y diámetro de orificio de válvulas de aire para "
    "llenado, vaciado/drenaje y purga, siguiendo la metodología del Manual AWWA M51 (2016)."
)

# ---------------------------------------------------------------------------
# 1. Carga y mapeo del perfil
# ---------------------------------------------------------------------------
st.header("1. Perfil de la conducción")

with st.expander("Formato esperado del archivo .csv", expanded=False):
    st.markdown(
        "El archivo debe tener al menos dos columnas numéricas: **cadenamiento** (m) y "
        "**elevación** (m), en cualquier orden y con cualquier nombre de encabezado — se piden "
        "a continuación. Puede descargar un perfil de ejemplo para probar la app."
    )
    try:
        with open("sample_profile.csv", "rb") as f:
            st.download_button("Descargar perfil de ejemplo", f, file_name="sample_profile.csv", mime="text/csv")
    except FileNotFoundError:
        pass

uploaded_file = st.file_uploader("Cargar perfil (.csv)", type=["csv"])

if uploaded_file is None:
    st.info("Cargue un archivo .csv con el perfil de la conducción para continuar.")
    st.stop()

try:
    raw_df = pd.read_csv(uploaded_file, sep=None, engine="python")
except Exception:
    uploaded_file.seek(0)
    raw_df = pd.read_csv(uploaded_file, sep=";")

# Manejo de coma decimal (formato es-LA) en columnas que deberían ser numéricas
for col in raw_df.columns:
    if raw_df[col].dtype == object:
        converted = pd.to_numeric(raw_df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        if converted.notna().mean() > 0.8:
            raw_df[col] = converted

st.dataframe(raw_df.head(8), use_container_width=True, height=220)

col_a, col_b = st.columns(2)
chainage_col = col_a.selectbox("Columna de cadenamiento (m)", raw_df.columns, index=0)
elevation_col = col_b.selectbox(
    "Columna de elevación (m)", raw_df.columns, index=min(1, len(raw_df.columns) - 1)
)

profile_df = pp.load_profile(raw_df, chainage_col, elevation_col)
if len(profile_df) < 3:
    st.error("El perfil necesita al menos 3 puntos válidos (cadenamiento y elevación numéricos).")
    st.stop()

st.caption(f"{len(profile_df)} puntos válidos cargados, de {profile_df['chainage_m'].min():.0f} m a {profile_df['chainage_m'].max():.0f} m.")

# ---------------------------------------------------------------------------
# 2. Parámetros hidráulicos y de tubería
# ---------------------------------------------------------------------------
st.header("2. Datos de la línea")

with st.form("parametros_form"):
    tipo_linea = st.radio("Tipo de línea", ["Impulsión", "Gravedad"], horizontal=True)

    if tipo_linea == "Impulsión":
        carga_val, carga_unit = number_with_unit(
            "Carga dinámica de bombeo inicial",
            20.0,
            HEAD_UNITS,
            "mwc",
            "carga_bombeo",
            help_text="Carga total a la salida de la bombeo (se suma a la elevación del cadenamiento 0 del perfil).",
        )
        nivel_tanque = None
    else:
        nivel_tanque = st.number_input(
            "Nivel de agua en el tanque (elevación, m — mismo datum que el perfil)",
            value=float(profile_df["elevation_m"].max() + 5),
        )
        carga_val, carga_unit = None, None

    caudal_val, caudal_unit = number_with_unit("Caudal de diseño", 50.0, FLOW_UNITS, "lps", "caudal", min_value=0.001)
    diam_val, diam_unit = number_with_unit("Diámetro interior de tubería", 300.0, LENGTH_UNITS, "mm", "diametro", min_value=0.001)

    col_mat, col_c = st.columns(2)
    material = col_mat.selectbox("Material", list(HAZEN_WILLIAMS_C.keys()))
    c_hw_default = HAZEN_WILLIAMS_C[material]
    c_hw = col_c.number_input("Coeficiente Hazen-Williams (C)", value=float(c_hw_default), min_value=60.0, max_value=200.0, help="Valor de diseño estándar según material; editable si se dispone de un dato específico.")

    dissolved_air_pct = st.select_slider(
        "% de aire disuelto para dimensionamiento de purga",
        options=DISSOLVED_AIR_PERCENT_OPTIONS,
        value=DISSOLVED_AIR_PERCENT_DEFAULT,
        help="Base del M51: 2% (solubilidad del aire en agua a condiciones estándar); 2–5% sugerido si hay gases disueltos adicionales.",
    )

    col_fv, col_dv = st.columns(2)
    fill_velocity_ms = col_fv.number_input(
        "Velocidad de llenado (m/s)", value=0.30, min_value=0.05, max_value=1.0, step=0.05,
        help="Recomendación M51: no exceder 1 ft/s (0.30 m/s).",
    )
    drain_velocity_ms = col_dv.number_input(
        "Velocidad de vaciado/drenaje (m/s)", value=0.46, min_value=0.10, max_value=1.0, step=0.05,
        help="Recomendación M51: 1–2 ft/s (0.30–0.60 m/s).",
    )

    col_sp, col_ms = st.columns(2)
    spacing_m = col_sp.slider("Espaciamiento de válvulas periódicas (m)", 400, 800, 500, step=50, help="Cada 1/4 a 1/2 milla (400–800 m) en tramos largos, según M51.")
    min_spacing_m = col_ms.number_input("Distancia mínima entre válvulas (m)", value=50.0, min_value=10.0)

    st.markdown("**Desfogues / drenajes (válvulas de seccionamiento)**")
    st.caption("El vaciado se calcula en la cresta más alta antes y después de cada desfogue, no en el desfogue mismo.")
    drains_df = st.data_editor(
        pd.DataFrame({"Cadenamiento (m)": pd.Series(dtype=float)}),
        num_rows="dynamic",
        use_container_width=True,
        key="drains_editor",
    )

    with st.expander("Avanzado: presión de colapso para vaciado (Ec. 4-4 / 4-5)"):
        usar_colapso = st.checkbox("Calcular ΔP de vaciado a partir de la presión de colapso de la tubería", value=False)
        col_e, col_sf = st.columns(2)
        espesor_val, espesor_unit = number_with_unit("Espesor de pared", 6.0, ["mm", "in"], "mm", "espesor", min_value=0.01)
        factor_seguridad = col_sf.number_input("Factor de seguridad", value=4.0, min_value=2.0, max_value=6.0, step=0.5)
        delta_p_drain_default = st.number_input("ΔP de vaciado por defecto (psi, si no se usa el cálculo de colapso)", value=5.0, min_value=0.5)

    delta_p_fill_psi = st.number_input("ΔP de venteo en llenado (psi)", value=2.0, min_value=0.5, help="Valor típico del M51 para venteo a presión atmosférica durante el llenado.")

    submitted = st.form_submit_button("▶ Calcular", use_container_width=True)

if not submitted and "results" not in st.session_state:
    st.stop()

# ---------------------------------------------------------------------------
# 3. Cálculo
# ---------------------------------------------------------------------------
if submitted:
    diameter_m = hyd.length_to_m(diam_val, diam_unit)
    flow_m3s = hyd.flow_to_m3s(caudal_val, caudal_unit)
    is_impulsion = tipo_linea == "Impulsión"

    x_start = float(profile_df["chainage_m"].iloc[0])
    e_start = float(profile_df["elevation_m"].iloc[0])

    if is_impulsion:
        carga_m = hyd.head_to_m(carga_val, carga_unit)
        hgl_start_m = e_start + carga_m
    else:
        hgl_start_m = float(nivel_tanque)

    gradient_j = hyd.hazen_williams_gradient(flow_m3s, diameter_m, c_hw)

    drain_chainages = [float(v) for v in drains_df["Cadenamiento (m)"].dropna().tolist()]

    locations_df, was_simplified = pp.build_valve_locations(
        profile_df,
        is_impulsion=is_impulsion,
        drain_chainages=drain_chainages,
        spacing_m=float(spacing_m),
        min_spacing_m=float(min_spacing_m),
    )

    if usar_colapso:
        espesor_in = hyd.m_to_in(hyd.length_to_m(espesor_val, espesor_unit))
        diam_in = hyd.m_to_in(diameter_m)
        p_colapso = vs.collapse_pressure_psi(espesor_in, diam_in)
        delta_p_drain_psi = vs.allowable_delta_p_psi(p_colapso, factor_seguridad)
    else:
        p_colapso = None
        delta_p_drain_psi = delta_p_drain_default

    rows = []
    for _, r in locations_df.iterrows():
        chainage = float(r["chainage_m"])
        elevation = float(r["elevation_m"])
        hgl_at_point = hyd.build_hgl(np.array([x_start, chainage]), hgl_start_m, gradient_j)[1]
        delta_p_purge_m = hgl_at_point - elevation

        purge = vs.purge_sizing(flow_m3s, dissolved_air_pct, delta_p_purge_m)
        fill = vs.filling_sizing(diameter_m, fill_velocity_ms, delta_p_fill_psi)
        drain = vs.draining_sizing(diameter_m, drain_velocity_ms, delta_p_drain_psi)
        governing_in = max(fill.diameter_in, drain.diameter_in)

        rows.append(
            {
                "Cadenamiento (m)": chainage,
                "Elevación (m)": elevation,
                "Tipo de válvula (Cap. 3 M51)": CATEGORY_LABELS.get(r["category"], r["category"]),
                "Ø Llenado/Vaciado (in)": governing_in,
                "Ø Llenado/Vaciado (mm)": governing_in * 25.4,
                "Ø Purga (in)": purge.diameter_in,
                "Ø Purga (mm)": purge.diameter_in * 25.4,
                "Presión de operación (mwc)": delta_p_purge_m,
                "Presión de operación (bar)": delta_p_purge_m / hyd.HEAD_TO_M["bar"],
                "Presión de operación (psi)": delta_p_purge_m / hyd.HEAD_TO_M["psi"],
                "HGL (m)": hgl_at_point,
                "_source": r["source"],
                "_fill_in": fill.diameter_in,
                "_drain_in": drain.diameter_in,
                "_fill_exceeds": fill.exceeds_largest,
                "_drain_exceeds": drain.exceeds_largest,
                "_purge_exceeds": purge.exceeds_largest,
                "_purge_na": purge.not_applicable,
                "_desfogues": ", ".join(f"{d:.0f}" for d in r["drain_refs"]) if r["drain_refs"] else "",
            }
        )

    results_df = pd.DataFrame(rows)

    st.session_state["results"] = {
        "results_df": results_df,
        "profile_df": profile_df,
        "hgl_start_m": hgl_start_m,
        "gradient_j": gradient_j,
        "x_start": x_start,
        "was_simplified": was_simplified,
        "p_colapso": p_colapso,
        "delta_p_drain_psi": delta_p_drain_psi,
    }

# ---------------------------------------------------------------------------
# 4. Resultados
# ---------------------------------------------------------------------------
state = st.session_state["results"]
results_df = state["results_df"]
profile_df = state["profile_df"]

st.header("3. Resultados")

if state["was_simplified"]:
    st.markdown(
        f'<div class="wv-banner">El perfil cargado tenía muchos nodos y fue discretizado '
        f"(simplificación de quiebres de pendiente) para obtener ubicaciones de válvula "
        f"coherentes. El gráfico y las elevaciones siguen usando el perfil completo.</div>",
        unsafe_allow_html=True,
    )
if state["p_colapso"] is not None:
    st.markdown(
        f'<div class="wv-banner">Presión de colapso calculada (Ec. 4-4): {state["p_colapso"]:.1f} psi → '
        f'ΔP admisible de vaciado (Ec. 4-5): {state["delta_p_drain_psi"]:.2f} psi.</div>',
        unsafe_allow_html=True,
    )

if results_df.empty:
    st.warning("No se identificaron ubicaciones de válvula con los parámetros actuales.")
else:
    display_df = results_df.drop(columns=[c for c in results_df.columns if c.startswith("_") and c != "_desfogues"]).rename(
        columns={"_desfogues": "Desfogues asociados (m)"}
    )
    st.dataframe(
        display_df.style.format(
            {
                "Cadenamiento (m)": "{:.0f}",
                "Elevación (m)": "{:.2f}",
                "Ø Llenado/Vaciado (in)": "{:.3f}",
                "Ø Llenado/Vaciado (mm)": "{:.1f}",
                "Ø Purga (in)": "{:.3f}",
                "Ø Purga (mm)": "{:.1f}",
                "Presión de operación (mwc)": "{:.1f}",
                "Presión de operación (bar)": "{:.2f}",
                "Presión de operación (psi)": "{:.1f}",
            }
        ),
        use_container_width=True,
        height=min(60 + 35 * len(display_df), 520),
    )

    if (results_df["Presión de operación (mwc)"] < 0).any():
        st.markdown(
            '<div class="wv-banner">⚠️ Uno o más puntos quedan por encima de la línea de energía '
            "(presión de operación negativa): esa sección de la línea no tendría carga suficiente "
            "para mantenerse presurizada con los datos actuales (carga de bombeo / nivel de tanque, "
            "caudal o diámetro). Revise esos parámetros antes de tomar los diámetros de purga como "
            "definitivos en esos puntos.</div>",
            unsafe_allow_html=True,
        )

    if results_df["_fill_exceeds"].any() or results_df["_drain_exceeds"].any() or results_df["_purge_exceeds"].any():
        st.markdown(
            '<div class="wv-banner">⚠️ Algún punto requiere más caudal de aire que el orificio más '
            "grande de la tabla del M51 (20 in / 1 in según tabla). Considere un cluster de válvulas "
            "(Tabla 4-4) o consulte al fabricante.</div>",
            unsafe_allow_html=True,
        )

    csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Descargar tabla de resultados (.csv)", csv_bytes, file_name="valvulas_aire_M51.csv", mime="text/csv")

    with st.expander("Detalle de cálculo por punto (llenado vs. vaciado por separado)"):
        detail_df = results_df[["Cadenamiento (m)", "_fill_in", "_drain_in"]].rename(
            columns={"_fill_in": "Ø Llenado (in)", "_drain_in": "Ø Vaciado (in)"}
        )
        st.dataframe(detail_df.style.format({"Cadenamiento (m)": "{:.0f}", "Ø Llenado (in)": "{:.3f}", "Ø Vaciado (in)": "{:.3f}"}), use_container_width=True)

    # -----------------------------------------------------------------
    # Gráfico: perfil + línea de energía + válvulas
    # -----------------------------------------------------------------
    st.subheader("Perfil, línea de energía (HGL) y válvulas sugeridas")

    hgl_full = hyd.build_hgl(profile_df["chainage_m"].to_numpy(), state["hgl_start_m"], state["gradient_j"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=profile_df["chainage_m"], y=profile_df["elevation_m"], mode="lines", name="Perfil / tubería",
            line=dict(width=2.5, color=PALETTE["ink"]), fill="tozeroy", fillcolor="rgba(11,41,66,0.06)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=profile_df["chainage_m"], y=hgl_full, mode="lines", name="Línea de energía (HGL)",
            line=dict(width=2, color=PALETTE["primary"], dash="dot"),
        )
    )

    for source, color in MARKER_COLOR_BY_SOURCE.items():
        subset = results_df[results_df["_source"] == source]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["Cadenamiento (m)"], y=subset["Elevación (m)"], mode="markers",
                name=source.replace("_", " ").capitalize(),
                marker=dict(size=11, color=color, line=dict(width=1, color="white"), symbol="diamond"),
                customdata=subset[["Tipo de válvula (Cap. 3 M51)", "Presión de operación (psi)", "Ø Llenado/Vaciado (in)", "Ø Purga (in)"]],
                hovertemplate=(
                    "Cadenamiento: %{x:.0f} m<br>Elevación: %{y:.2f} m<br>%{customdata[0]}<br>"
                    "P. operación: %{customdata[1]:.1f} psi<br>Ø Llenado/Vaciado: %{customdata[2]:.2f} in<br>"
                    "Ø Purga: %{customdata[3]:.2f} in<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=520,
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis_title="Cadenamiento (m)",
        yaxis_title="Elevación (m)",
        hovermode="closest",
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
