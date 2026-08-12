import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import hydraulics as hyd
import profile_processing as pp
import valve_sizing as vs
from m51_tables import DISSOLVED_AIR_PERCENT_DEFAULT, DISSOLVED_AIR_PERCENT_OPTIONS, HAZEN_WILLIAMS_C, MANNING_N_BY_MATERIAL
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
    "riesgo_arrastre_aire": "Riesgo de arrastre de aire (PGA, UNAM) + descompresión (Wang et al. 2023)",
    "periodico_ascenso": "Punto periódico — ascenso largo",
    "periodico_horizontal": "Punto periódico — tramo horizontal",
    "periodico_descenso": "Punto periódico — descenso largo",
}

SCFM_TO_M3H = 1.699011  # 1 SCFM = 0.0283168 m3/min * 60 min/hr


def number_with_unit(label, default_value, units, default_unit, key, help_text=None, min_value=0.0):
    col1, col2 = st.columns([3, 1])
    value = col1.number_input(label, min_value=min_value, value=default_value, key=f"{key}_val", help=help_text)
    unit = col2.selectbox("unidad", units, index=units.index(default_unit), key=f"{key}_unit", label_visibility="visible")
    return value, unit


def render_profile_chart(profile_df, hgl_series=None, valve_df=None, drain_points=None, height=440):
    """Perfil + (opcional) línea de energía + marcadores de válvulas/desfogues,
    con el eje Y autoescalado al rango real de los datos (sin forzar el 0)."""
    y_values = [float(profile_df["elevation_m"].min()), float(profile_df["elevation_m"].max())]
    if hgl_series is not None:
        y_values += [float(np.min(hgl_series)), float(np.max(hgl_series))]
    if valve_df is not None and not valve_df.empty:
        y_values += [float(valve_df["Elevación (m)"].min()), float(valve_df["Elevación (m)"].max())]
    if drain_points:
        y_values += [p[1] for p in drain_points]
    y_min, y_max = min(y_values), max(y_values)
    pad = max((y_max - y_min) * 0.10, 1.0)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=profile_df["chainage_m"], y=profile_df["elevation_m"], mode="lines", name="Perfil / tubería",
            line=dict(width=2.5, color=PALETTE["ink"]),
        )
    )
    if hgl_series is not None:
        fig.add_trace(
            go.Scatter(
                x=profile_df["chainage_m"], y=hgl_series, mode="lines", name="Línea de energía (HGL)",
                line=dict(width=2, color=PALETTE["primary"], dash="dot"),
            )
        )
    if valve_df is not None and not valve_df.empty:
        has_hover_info = "Tipo de válvula (Cap. 3 M51)" in valve_df.columns and "Presión de operación (psi)" in valve_df.columns
        fig.add_trace(
            go.Scatter(
                x=valve_df["Cadenamiento (m)"], y=valve_df["Elevación (m)"], mode="markers",
                name="Válvulas de aire propuestas",
                marker=dict(size=11, color=PALETTE["deep"], symbol="diamond", line=dict(width=1, color="white")),
                customdata=valve_df[["Tipo de válvula (Cap. 3 M51)", "Presión de operación (psi)"]] if has_hover_info else None,
                hovertemplate=(
                    "Cadenamiento: %{x:.0f} m<br>Elevación: %{y:.2f} m"
                    + ("<br>%{customdata[0]}<br>P. operación: %{customdata[1]:.1f} psi" if has_hover_info else "")
                    + "<extra></extra>"
                ),
            )
        )
    if drain_points:
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in drain_points], y=[p[1] for p in drain_points], mode="markers",
                name="Desfogues declarados",
                marker=dict(size=13, color=PALETTE["warn"], symbol="triangle-down", line=dict(width=1, color="white")),
                hovertemplate="Desfogue<br>Cadenamiento: %{x:.0f} m<br>Elevación: %{y:.2f} m<extra></extra>",
            )
        )

    fig.update_layout(
        height=height,
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis_title="Cadenamiento (m)",
        yaxis_title="Elevación (m)",
        yaxis=dict(range=[y_min - pad, y_max + pad]),
        hovermode="closest",
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
        plot_bgcolor="white",
    )
    return fig


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

def _decode_csv_bytes(raw_bytes: bytes) -> str:
    """Prueba UTF-8 y, si falla, codificaciones típicas de CSV exportados desde
    Excel en Windows en español (cp1252/latin-1) antes de rendirse."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace")


def _parse_csv_text(text: str) -> pd.DataFrame:
    for sep in (None, ";", ",", "\t"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
            if df.shape[1] >= 2:
                return df
        except Exception:
            continue
    raise ValueError("No se pudo interpretar el archivo: revise que sea un .csv con columnas separadas por coma, punto y coma o tabulador.")


try:
    raw_df = _parse_csv_text(_decode_csv_bytes(uploaded_file.getvalue()))
except Exception as exc:
    st.error(f"No se pudo leer el archivo cargado: {exc}")
    st.stop()

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
st.plotly_chart(render_profile_chart(profile_df, height=320), use_container_width=True)

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

    col_sp, col_tol = st.columns(2)
    spacing_m = col_sp.slider("Espaciamiento de válvulas periódicas (m)", 400, 800, 500, step=50, help="Cada 1/4 a 1/2 milla (400–800 m) en tramos largos, según M51.")
    slope_tolerance_m = col_tol.slider(
        "Sensibilidad de detección de quiebres de pendiente (m)", 0.2, 5.0, 2.0, step=0.1,
        help="Filtra ruido/redondeo de la topografía antes de ubicar válvulas. Valores bajos detectan más quiebres "
        "(más válvulas); valores altos solo detectan quiebres importantes (menos válvulas, resultado más coherente "
        "en perfiles reales con cotas redondeadas). Ajuste y vuelva a calcular si el resultado tiene demasiadas o "
        "muy pocas válvulas.",
    )

    st.markdown("**Presiones diferenciales (ΔP)**")
    st.caption(
        "El ΔP de llenado (venteo, aire saliendo) y el de vaciado (admisión, aire entrando) NO son intercambiables: "
        "un mismo orificio tiene capacidades distintas para cada sentido de flujo (M51 Tabla 4-2 vs. 4-3), y la "
        "admisión además se satura a flujo sónico para presiones internas ≲0.53 × atmosférica."
    )
    col_dpf, col_dpd = st.columns(2)
    delta_p_fill_psi = col_dpf.number_input(
        "ΔP de llenado (psi)", value=2.0, min_value=0.5, help="Valor típico del M51 para venteo a presión atmosférica durante el llenado."
    )
    delta_p_drain_psi_input = col_dpd.number_input(
        "ΔP de vaciado (psi)", value=5.0, min_value=0.5,
        help="Valor típico del M51 cuando la tubería no es propensa a colapso. Se puede reemplazar por un cálculo "
        "de presión de colapso real en el panel avanzado.",
    )

    st.markdown("**Desfogues / drenajes (válvulas de seccionamiento)**")
    st.caption(
        "El vaciado se calcula en la cresta más alta antes y después de cada desfogue (no en el desfogue mismo), "
        "usando la pendiente real de la tubería entre la cresta y el desfogue (M51 pág. 28–32, flujo por gravedad)."
    )
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

    with st.expander("Avanzado: riesgo de arrastre de aire + descompresión tras rotura (UNAM + Wang et al. 2023)"):
        st.caption(
            "Identifica tramos descendentes donde el flujo no alcanza velocidad suficiente para arrastrar aire "
            "hacia aguas abajo (parámetro de gasto adimensional PGA = Q²/(g·D⁵) menor que la pendiente del tubo, "
            "UNAM Ec. 3.6). Dentro de esos tramos, si el desnivel acumulado supera el valor de control de vacío "
            "tras una rotura de tubería (Wang et al. 2023, Ec. 9-11), se agrega una válvula intermedia en el punto "
            "más crítico. Solo actúa sobre tramos realmente en riesgo, no sobre todo el perfil."
        )
        usar_wang = st.checkbox("Activar verificación de riesgo de arrastre de aire", value=False)
        col_dh, col_sc = st.columns(2)
        delta_h_max_m = col_dh.number_input("ΔH máx. de control de vacío (m)", value=8.0, min_value=1.0, help="Valor típico según Wang et al. (2023).")
        soil_cover_m = col_sc.number_input("Recubrimiento de suelo si es enterrada (m)", value=0.0, min_value=0.0)

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
    drain_points = [(d, hyd.elevation_at_chainage(profile_df, d)) for d in drain_chainages]

    locations_df, was_simplified = pp.build_valve_locations(
        profile_df,
        is_impulsion=is_impulsion,
        drain_chainages=drain_chainages,
        spacing_m=float(spacing_m),
        slope_tolerance_m=float(slope_tolerance_m),
        delta_h_max_m=float(delta_h_max_m) if usar_wang else None,
        soil_cover_m=float(soil_cover_m),
        flow_m3s=flow_m3s,
        diameter_m=diameter_m,
    )

    manning_n = MANNING_N_BY_MATERIAL[material]

    if usar_colapso:
        espesor_in = hyd.m_to_in(hyd.length_to_m(espesor_val, espesor_unit))
        diam_in = hyd.m_to_in(diameter_m)
        p_colapso = vs.collapse_pressure_psi(espesor_in, diam_in)
        delta_p_drain_psi = vs.allowable_delta_p_psi(p_colapso, factor_seguridad)
    else:
        p_colapso = None
        delta_p_drain_psi = delta_p_drain_psi_input

    rows = []
    for _, r in locations_df.iterrows():
        chainage = float(r["chainage_m"])
        elevation = float(r["elevation_m"])
        hgl_at_point = hyd.build_hgl(np.array([x_start, chainage]), hgl_start_m, gradient_j)[1]
        delta_p_purge_m = hgl_at_point - elevation

        purge = vs.purge_sizing(flow_m3s, dissolved_air_pct, delta_p_purge_m)
        fill = vs.filling_sizing(diameter_m, fill_velocity_ms, delta_p_fill_psi)
        drain = vs.draining_sizing(diameter_m, drain_velocity_ms, delta_p_drain_psi)

        # En crestas adyacentes a un desfogue declarado, el M51 (pag. 28-32) dimensiona el
        # vaciado por flujo de gravedad segun la pendiente real hacia el desfogue, no por una
        # velocidad de vaciado supuesta: se toma el caudal gobernante entre ambos metodos.
        if r["drain_refs"]:
            governing_drain_scfm = drain.required_scfm
            for drain_c in r["drain_refs"]:
                drain_elev = hyd.elevation_at_chainage(profile_df, drain_c)
                run_length = abs(drain_c - chainage)
                if run_length > 0:
                    slope = abs(elevation - drain_elev) / run_length
                    gravity_scfm = vs.gravity_flow_scfm(diameter_m, slope, manning_n)
                    governing_drain_scfm = max(governing_drain_scfm, gravity_scfm)
            drain = vs.draining_result_from_scfm(governing_drain_scfm, delta_p_drain_psi)

        governing_air_m3h = max(fill.required_scfm, drain.required_scfm) * SCFM_TO_M3H

        rows.append(
            {
                "Cadenamiento (m)": chainage,
                "Elevación (m)": elevation,
                "Tipo de válvula (Cap. 3 M51)": CATEGORY_LABELS.get(r["category"], r["category"]),
                "Caudal de aire llenado/vaciado (m³/hr)": governing_air_m3h,
                "Ø Purga (in)": purge.diameter_in,
                "Ø Purga (mm)": purge.diameter_in * 25.4,
                "Presión de operación (mwc)": delta_p_purge_m,
                "Presión de operación (bar)": delta_p_purge_m / hyd.HEAD_TO_M["bar"],
                "Presión de operación (psi)": delta_p_purge_m / hyd.HEAD_TO_M["psi"],
                "HGL (m)": hgl_at_point,
                "_source": r["source"],
                "_fill_m3h": fill.required_scfm * SCFM_TO_M3H,
                "_drain_m3h": drain.required_scfm * SCFM_TO_M3H,
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
        "drain_points": drain_points,
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
                "Caudal de aire llenado/vaciado (m³/hr)": "{:.1f}",
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
        detail_df = results_df[["Cadenamiento (m)", "_fill_m3h", "_drain_m3h"]].rename(
            columns={"_fill_m3h": "Caudal llenado (m³/hr)", "_drain_m3h": "Caudal vaciado (m³/hr)"}
        )
        st.dataframe(
            detail_df.style.format({"Cadenamiento (m)": "{:.0f}", "Caudal llenado (m³/hr)": "{:.1f}", "Caudal vaciado (m³/hr)": "{:.1f}"}),
            use_container_width=True,
        )

    # -----------------------------------------------------------------
    # Gráfico: perfil + línea de energía + válvulas + desfogues
    # -----------------------------------------------------------------
    st.subheader("Perfil, línea de energía (HGL) y válvulas sugeridas")

    hgl_full = hyd.build_hgl(profile_df["chainage_m"].to_numpy(), state["hgl_start_m"], state["gradient_j"])

    fig = render_profile_chart(
        profile_df, hgl_series=hgl_full, valve_df=results_df, drain_points=state.get("drain_points"), height=520
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Referencias técnicas
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="font-size:11px; color:#6B7280; margin-top:24px; border-top:1px solid #E5E7EB; padding-top:10px;">
    <strong>Referencias técnicas:</strong><br>
    • American Water Works Association. 2016. <em>Manual of Water Supply Practices M51: Air Valves — Air-Release,
    Air/Vacuum, and Combination</em>, 2nd ed. Denver, CO: AWWA. (Dimensionamiento de orificio, Tablas 4-1 a 4-4;
    localización, Fig. 3-1).<br>
    • Pozos-Estrada, O., Fairuzov, Y., Sánchez-Huerta, A., Rodal-Canales, E.A. 2012. <em>Manual de análisis de la
    problemática del aire atrapado en acueductos para mejorar su eficiencia</em>. Serie Manuales SM13, Instituto de
    Ingeniería, UNAM. (Localización de válvulas de aire, sec. 1.5; criterio de arrastre de burbujas Q²/gD⁵, sec. 3.2).<br>
    • Wang, Y., Zhang, J., Xu, T., Liu, Y., Yao, T., Wang, K., Zhang, M. 2023. "Air valve arrangement criteria for
    preventing secondary pipe bursts in long-distance gravitational water supply systems." <em>AQUA — Water
    Infrastructure, Ecosystems and Society</em>, 72(8), 1566–1581. (Desnivel máximo admisible entre válvulas
    adyacentes, Ec. 9-11).<br>
    • Kalinske, A.A., Bliss, P.H. 1943. "Removal of air from pipe lines by flowing water." <em>Civil Engineering</em>,
    13(10). (Origen del parámetro de gasto adimensional Q²/gD⁵ usado por los criterios anteriores).
    </div>
    """,
    unsafe_allow_html=True,
)
