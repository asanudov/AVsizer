# Dimensionamiento y localización de válvulas de aire — AWWA M51

App en Streamlit que, a partir del perfil de una línea de conducción (cadenamiento/elevación
en un `.csv`), sugiere ubicación y dimensiona válvulas de aire para los escenarios de
**llenado**, **vaciado/drenaje** y **purga**, siguiendo la metodología de los capítulos 3 y 4
del *AWWA Manual M51 (2016), Air Valves: Air-Release, Air/Vacuum and Combination*.

## Alcance

- Ubicación de válvulas según las reglas de la Fig. 3-1 del M51 (puntos altos/bajos, quiebres
  de pendiente, tramos horizontales/ascensos/descensos largos cada 400–800 m, y puntos de
  vaciado en las crestas adyacentes a desfogues declarados).
- Dimensionamiento de orificio por interpolación directa de las Tablas 4-1 (purga), 4-2
  (llenado) y 4-3 (vaciado/vacío) del manual — no se reinventan las fórmulas de flujo
  compresible, se usan las tablas publicadas tal como indica el método del manual.
- Línea de gradiente hidráulico (HGL) por Hazen-Williams (fórmula métrica) para obtener la
  presión de operación en cada válvula.
- Fuera de alcance de esta primera versión: dimensionamiento de vacío por rotura de línea
  (Ecs. 4-7 a 4-13 del M51) y armado de clusters de válvulas (Tabla 4-4, incluida solo como
  referencia).

## Ejecutar localmente

```bash
cd air_valve_sizing
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

| Archivo | Contenido |
|---|---|
| `app.py` | Interfaz Streamlit (formularios, tabla de resultados, gráfico) |
| `m51_tables.py` | Tablas 4-1 a 4-4 del manual, transcritas del PDF |
| `valve_sizing.py` | Selección de orificio por escenario (interpolación de tablas) |
| `hydraulics.py` | Conversión de unidades y Hazen-Williams |
| `profile_processing.py` | Limpieza de CSV, simplificación (RDP) y localización de válvulas (Cap. 3) |
| `styling.py` | Tipografía Space Grotesk embebida + paleta de colores |
| `sample_profile.csv` | Perfil de ejemplo que ejercita todas las reglas del Cap. 3 |

## Despliegue

**Recomendado: [Streamlit Community Cloud](https://streamlit.io/cloud)** (gratuito, ya tiene
cuenta): suba esta carpeta a un repositorio de GitHub y conéctelo desde
`share.streamlit.io` señalando `air_valve_sizing/app.py` como archivo principal. No requiere
configuración adicional; los assets de fuente van embebidos en el propio código (no dependen
de CDN externo).

Alternativas si en el futuro necesita autenticación, más cómputo, o correr detrás de su propio
dominio:

- **Render / Railway**: despliegue con `Dockerfile` simple (`streamlit run app.py --server.port $PORT --server.address 0.0.0.0`).
- **Azure App Service / Container Apps**: si la organización ya usa Azure, es la opción más
  directa para integrarlo con SSO corporativo.

No se inicializó un repositorio Git en esta carpeta — indíquelo si quiere que se prepare el
repo y se conecte al despliegue.
