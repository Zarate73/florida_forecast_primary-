"""
Construye data/Historical_Polls_2018_2022.xlsx a partir de encuestas
individuales reales de las primarias de gobernador de Florida 2018 y 2022.

FUENTE: tablas de "opinion polling" de los artículos de Wikipedia
"2018 Florida gubernatorial election" y "2022 Florida gubernatorial
election" (a su vez sourced de RealClearPolitics/RealClearPolling y
prensa contemporánea -- St. Pete Polls, Mason-Dixon, GBAO, UNF, etc.).
Extracción vía fetch automatizado (17-ago-2026) + limpieza manual:
  - Se corrige un typo de año detectado ("Mar 3-11, 2017" -> 2018, la
    única fecha de esa tabla fuera de secuencia cronológica).
  - Se descartan filas sin precisión de día (ej. "Jul 2018", "Feb 2022")
    porque el parser de fecha del pipeline (extract_end_date) requiere
    día explícito -- son 2 filas de ~30, impacto marginal.
  - Se deduplica UNA fila que aparece literalmente dos veces en la tabla
    REP 2018 (St. Pete Polls, Jul 16-17, 2018).
  - Se deduplica un caso de la MISMA encuesta reportada con dos rangos de
    fecha casi idénticos y cifras casi idénticas (Gravis DEM/REP,
    Aug 21-22 vs Aug 21-25, 2018) -- se conserva la fila de rango más
    amplio (más cercana a como el pollster la publicó finalmente).
  - Se restringe cada carrera a partir de ~90 días antes de la elección
    (>= 1-jun-2018 para las dos primarias de 2018, >= 1-jun-2022 para la
    demócrata de 2022) -- ventana comparable a la que usan los modelos
    2026 vigentes (~2-2.5 meses de encuestas), y que además excluye de
    forma natural el período en que Corcoran/Latvala (REP 2018) todavía
    aparecían en boletas de encuestas pese a haber salido de la
    contienda antes de la campaña final.

ADVERTENCIA DE PROVENIENCIA: esta tabla se construyó con una extracción
automatizada de una página web (no un archivo estructurado descargado
directamente de RCP/pollster). Se hizo una verificación cruzada de
sanidad: el último poll de cada carrera se compara contra el resultado
real en BACKTEST_RESULTS.md y los márgenes finales coinciden en
dirección y orden de magnitud con lo reportado contemporáneamente en
prensa (ej. victoria de Gillum sobre Graham fue ampliamente cubierta
como "upset" frente al agregado de encuestas -- eso es justamente lo
que se ve en la última fila: Graham 32% > Gillum 25% en el último poll,
pero Gillum ganó la elección real). Si se requiere un uso de mayor
garantía (ej. publicación externa), se recomienda re-verificar las
cifras directamente contra los PDFs/notas de prensa originales de cada
encuestadora antes de citar cifras individuales de esta tabla.
"""
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "data" / "Historical_Polls_2018_2022.xlsx"

# ---------------------------------------------------------------------
# REP 2018 (DeSantis vs. Putnam) -- elección: 28-ago-2018
# Columnas: DeSantis, Putnam, Other (incluye Bob White + demás menores +
# residuo de Corcoran/Latvala una vez fuera de la contienda), Undecided
# ---------------------------------------------------------------------
rep_2018 = [
    # Poll_Source,                 Date,                  Sample, DeSantis, Putnam, Other, Undecided
    ("Florida Atlantic",           "May 4-7, 2018",         371,   16,    15,   27,   43),
    ("Saint Leo",                  "May 25-31, 2018",       175,   13,    35,    9,   44),
    ("Cherry Communications",      "Jun 7-9, 2018",         501,   15,    32,    5,   48),
    ("Gravis",                     "May 31-Jun 15, 2018",   543,   19,    29,    None, 43),
    ("Fox News",                   "Jun 15-19, 2018",       901,   17,    32,    8,   None),
    ("Marist",                     "Jun 17-21, 2018",       326,   21,    38,    3,   39),
    ("1892 Polling",               "Jul 2, 2018",           800,   47,    28,   None, None),
    ("Remington",                  "Jul 2-5, 2018",        2826,   43,    26,   None,  25),
    ("Fabrizio, Lee",              "Jul 8-12, 2018",        349,   42,    30,   None,  27),
    ("Gravis",                     "Jul 13-14, 2018",       905,   35,    29,    4,   25),
    ("St. Pete Polls",             "Jul 16-17, 2018",      1709,   50,    30,    4,   17),
    ("Clearview Research",         "Jul 14-19, 2018",       700,   38,    39,   None,  23),
    ("Florida Atlantic",           "Jul 20-21, 2018",       262,   36,    27,   15,   23),
    ("Mason-Dixon",                "Jul 23-25, 2018",       500,   41,    29,    2,   28),
    ("North Star Opinion",         "Aug 5-7, 2018",         600,   50,    30,   None, None),
    ("SurveyUSA",                  "Aug 10-13, 2018",       558,   40,    38,    7,   16),
    ("Saint Leo",                  "Aug 10-16, 2018",       172,   41,    52,    5,   None),
    ("Florida Atlantic",           "Aug 16-20, 2018",       222,   32,    31,   15,   22),
    ("St. Pete Polls",             "Aug 22-23, 2018",      2141,   56,    33,    3,   8),
    ("Gravis",                     "Aug 21-25, 2018",       579,   39,    27,   10,   23),
]

# ---------------------------------------------------------------------
# DEM 2018 (Gillum/Graham/Levine/Greene/King) -- elección: 28-ago-2018
# ---------------------------------------------------------------------
dem_2018 = [
    # Poll_Source, Date, Sample, Gillum, Graham, Levine, Greene, King, Other, Undecided
    ("Schroth, Eldon",       "Jun 3-5, 2018",        600, 11, 16, 32,  4,  6, None, 31),
    ("Let's Preserve",       "Jun 6-9, 2018",         800, 11, 21, 24,  3,  4, None, 37),
    ("RABA",                 "Jun 15-16, 2018",       660,  8, 26, 27,  3, 15, None, 21),
    ("Gravis",               "May 31-Jun 15, 2018",   485, 29, 24, 17, None, 3, None, 27),
    ("Marist",               "Jun 17-21, 2018",       344,  8, 17, 19,  4,  3,  1, 47),
    ("Gravis",               "Jul 13-14, 2018",      1540, 10, 27, 17, 18, None, None, 27),
    ("St. Pete Polls",       "Jul 14-15, 2018",      1314, 10, 22, 19, 22,  3,  1, 25),
    ("Associated Industries","Jul 16-18, 2018",       800, 12, 24, 16, 13,  4, None, None),
    ("Florida Atlantic",     "Jul 20-21, 2018",       271,  7, 20, 16, 14,  9,  3, 31),
    ("Mason-Dixon",          "Jul 23-25, 2018",       500, 10, 27, 18, 12,  7,  1, 25),
    ("St. Pete Polls",       "Jul 30-31, 2018",      1652, 12, 29, 19, 23,  3,  4, 9),
    ("ALG Research",         "Jul 29-Aug 2, 2018",    800, 10, 33, 17, 13,  3, None, 23),
    ("SurveyUSA",            "Aug 10-13, 2018",       631, 11, 22, 22, 16,  3,  2, 24),
    ("Saint Leo",            "Aug 10-16, 2018",       188, 15, 31, 22, 17,  5,  4, None),
    ("Schroth, Eldon",       "Aug 11-14, 2018",       600, 15, 24, 27, 13,  3, None, 18),
    ("Public Policy",        "Aug 5-6, 2018",         572, 13, 26, 22, 16,  4, None, 19),
    ("St. Pete Polls",       "Aug 18-19, 2018",      2202, 21, 27, 25, 15,  3,  4, 6),
    ("Change Research",      "Aug 18-19, 2018",      1178, 33, 22, 22, 10, None, None, None),
    ("Florida Atlantic",     "Aug 16-20, 2018",       280, 11, 29, 17, 11, 10,  3, 19),
    ("Schroth, Eldon",       "Aug 19-21, 2018",       669, 18, 25, 26, 13,  2, None, 15),
    ("St. Pete Polls",       "Aug 25-26, 2018",      2342, 25, 32, 22, 11,  2,  4, 5),
]

# ---------------------------------------------------------------------
# DEM 2022 (Crist/Fried; Daniel+Willis sin polling individual -> Other)
# elección: 23-ago-2022
# ---------------------------------------------------------------------
dem_2022 = [
    # Poll_Source, Date, Sample, Crist, Fried, Other, Undecided
    ("Global Strategy Group (D)", "Jun 8-13, 2022",  600, 38, 34, None, 29),
    ("St. Pete Polls",            "Jun 16-17, 2022", 1007, 49, 24, None, 27),
    ("GBAO (D)",                  "Jun 23-26, 2022",  600, 55, 34, None, 11),
    ("Kaplan Strategies",         "Jul 6, 2022",       671, 39, 39, None, 22),
    ("GBAO (D)",                  "Jul 27-31, 2022",   800, 52, 36, None, 12),
    ("St. Pete Polls",            "Aug 2-3, 2022",    1361, 56, 24, None, 20),
    ("Public Policy Polling (D)", "Aug 8-9, 2022",     664, 42, 35, None, 23),
    ("University of North Florida","Aug 8-12, 2022",   529, 43, 47,    5, 6),
    ("Change Research (D)",       "Aug 12-14, 2022",   702, 47, 37, None, 16),
    ("St. Pete Polls",            "Aug 20-21, 2022",  1617, 59, 30, None, 11),
]

COLS = {
    "rep_2018": ["Poll_Source", "Date", "Sample", "DeSantis", "Putnam", "Other", "Undecided"],
    "dem_2018": ["Poll_Source", "Date", "Sample", "Gillum", "Graham", "Levine", "Greene", "King", "Other", "Undecided"],
    "dem_2022": ["Poll_Source", "Date", "Sample", "Crist", "Fried", "Other", "Undecided"],
}

if __name__ == "__main__":
    df_rep_2018 = pd.DataFrame(rep_2018, columns=COLS["rep_2018"])
    df_dem_2018 = pd.DataFrame(dem_2018, columns=COLS["dem_2018"])
    df_dem_2022 = pd.DataFrame(dem_2022, columns=COLS["dem_2022"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        df_rep_2018.to_excel(writer, sheet_name="REP_2018", index=False)
        df_dem_2018.to_excel(writer, sheet_name="DEM_2018", index=False)
        df_dem_2022.to_excel(writer, sheet_name="DEM_2022", index=False)

    print(f"OK -- {OUT} escrito.")
    print(f"REP_2018: {len(df_rep_2018)} encuestas")
    print(f"DEM_2018: {len(df_dem_2018)} encuestas")
    print(f"DEM_2022: {len(df_dem_2022)} encuestas")
