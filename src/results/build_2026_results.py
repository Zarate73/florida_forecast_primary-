"""
Construye data/Florida_Governor_Primary_2026_Results.xlsx con el resultado
REAL de la primaria de gobernador de Florida del 18-ago-2026.

ESTADO DEL DATO: PRELIMINAR, NO CERTIFICADO. Fuente: News4Jax (atribuido a
recuento de AP), corte a 99.2% de precintas reportadas (5,584 / 5,631),
consultado el 19-ago-2026. Es consistente con el corte anterior de WFTV a
92% de conteo (Donalds 47.9%/Collins 25.1% REP; Jolly 61.0%/Foster 15.1%
DEM), señal de que el conteo ya estaba estabilizado -- pero NO es el
resultado certificado por el Florida Division of Elections (la
certificación oficial ocurre ~10 días después de la primaria). Ninguna de
las dos carreras tiene un margen remotamente cerca de disparar un
recuento (0.5% máquina / 0.25% manual), así que es improbable que la
certificación mueva la aguja -- pero "improbable" no es "verificado", y
este archivo debe refrescarse con el canvass oficial cuando esté
disponible.

REPUBLICANA -- nota sobre "Other_Minor": News4Jax reportó los 4
candidatos con apoyo relevante (Donalds/Collins/Fishback/Renner) con
porcentajes REDONDEADOS a enteros que suman 92%, no 100% -- el 8%
restante corresponde a 7 candidatos menores sin apoyo relevante (Jim
Holcomb, Arthur Joseph McCaffrey, Daniel Nokovich, Rachel Rodriguez,
James W. Shaw, Caneste Succe, Bobby Williams; lista oficial de
candidatos vía Florida Division of Elections), para los que NO se
encontró un desglose individual de votos en la búsqueda. Statewide_Votes
y Party_Total_Votes de esos 7 candidatos y del bucket "Other_Minor_REP"
son, por lo tanto, ESTIMADOS por resta (Total implícito = suma de los 4
conocidos / 0.92; Other = Total implícito - suma de los 4 conocidos),
NO un conteo directo -- ver columna Vote_Count_Type.

DEMÓCRATA -- los 6 candidatos de la boleta oficial SÍ tienen conteo
individual completo (News4Jax), suman ~100% sin residuo -- no hace falta
estimar nada por resta.
"""
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "data" / "Florida_Governor_Primary_2026_Results.xlsx"

SOURCE = "News4Jax (atribuido a AP), consultado 19-ago-2026"
SOURCE_URL = "https://www.news4jax.com/vote-2026/2026/08/17/vote-2026-election-results-for-florida-governor-primaries-on-aug-18-2026/"
DATA_STATUS = "PRELIMINAR -- 99.2% de precintas reportadas (5,584/5,631), no certificado por FL Division of Elections"
PCT_PRECINCTS_REPORTING = 99.2

# --- Republicana: conteo directo para los 4 con apoyo relevante ---
rep_counted = {
    "Donalds":  810_033,
    "Collins":  426_413,
    "Fishback": 177_526,
    "Renner":   144_830,
}
rep_counted_sum = sum(rep_counted.values())
rep_counted_pct_sum = 0.92  # 48% + 25% + 10% + 9%, según News4Jax (redondeado)
rep_total_estimated = rep_counted_sum / rep_counted_pct_sum
rep_other_estimated = rep_total_estimated - rep_counted_sum

rep_rows = []
for i, (cand, votes) in enumerate(rep_counted.items(), start=1):
    rep_rows.append({
        "Year": 2026, "PartyCode": "REP", "PartyName": "Republican", "Candidate": cand,
        "Statewide_Votes": votes, "Party_Total_Votes": round(rep_total_estimated),
        "Vote_Share": votes / rep_total_estimated, "Party_Rank": i,
        "Vote_Count_Type": "Directo (News4Jax)",
    })
rep_rows.append({
    "Year": 2026, "PartyCode": "REP", "PartyName": "Republican",
    "Candidate": "Other_Minor (Holcomb, McCaffrey, Nokovich, Rodriguez, Shaw, Succe, Williams)",
    "Statewide_Votes": round(rep_other_estimated), "Party_Total_Votes": round(rep_total_estimated),
    "Vote_Share": rep_other_estimated / rep_total_estimated, "Party_Rank": 5,
    "Vote_Count_Type": "ESTIMADO por resta (ver docstring) -- no es un conteo directo",
})

# --- Demócrata: conteo directo y completo para los 6 candidatos ---
dem_counted = {
    "Jolly":          760_073,
    "Foster":         188_623,
    "Joseph":         119_410,
    "Castillo-Bach":   96_393,
    "Fernandez":       47_180,
    "Norman":          34_875,
}
dem_total = sum(dem_counted.values())

dem_rows = []
for i, (cand, votes) in enumerate(dem_counted.items(), start=1):
    dem_rows.append({
        "Year": 2026, "PartyCode": "DEM", "PartyName": "Democrat", "Candidate": cand,
        "Statewide_Votes": votes, "Party_Total_Votes": dem_total,
        "Vote_Share": votes / dem_total, "Party_Rank": i,
        "Vote_Count_Type": "Directo (News4Jax)",
    })

if __name__ == "__main__":
    df = pd.DataFrame(rep_rows + dem_rows)
    df = df.sort_values(["PartyCode", "Party_Rank"]).reset_index(drop=True)

    meta = pd.DataFrame([
        {"Campo": "Elección", "Valor": "Primaria de Gobernador de Florida, 18-ago-2026"},
        {"Campo": "Estado del dato", "Valor": DATA_STATUS},
        {"Campo": "Pct_Precincts_Reporting", "Valor": PCT_PRECINCTS_REPORTING},
        {"Campo": "Fuente", "Valor": SOURCE},
        {"Campo": "URL fuente", "Valor": SOURCE_URL},
        {"Campo": "Ganador REP proyectado (AP)", "Valor": "Byron Donalds"},
        {"Campo": "Ganador DEM proyectado (AP)", "Valor": "David Jolly"},
        {"Campo": "Advertencia REP", "Valor": "Other_Minor REP es ESTIMADO por resta, no conteo directo -- ver Vote_Count_Type"},
        {"Campo": "Pendiente", "Valor": "Refrescar con canvass oficial certificado del FL Division of Elections (~10 dias post-eleccion)"},
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        meta.to_excel(writer, sheet_name="Metadata", index=False)
        df.to_excel(writer, sheet_name="Statewide_Summary_2026", index=False)

    print(f"OK -- {OUT} escrito.")
    print(df.to_string(index=False))
