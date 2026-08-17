import pandas as pd
import numpy as np
import re
import scipy.stats as stats

# =====================================================================
# CELDA "1. Ingesta y Limpieza" -- CORREGIDA v2
# =====================================================================
print("Cargando archivos de datos...")

polls_rep = pd.read_excel('Florida_Polls_Clean_2026Primary.xlsx', sheet_name='Rep_Primary_Polls')
ev_summary = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Summary_by_County')
ev_demographics = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Full_Data')
ev_statewide = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Statewide_Totals')
turnout_hist = pd.read_excel('Florida_Governor_Primary_Turnout_2018_2022.xlsx', sheet_name='Turnout_by_County')

print("Limpiando base de encuestas...")

TODAY = pd.Timestamp('2026-08-17')


def extract_end_date(date_str, reference_date=TODAY):
    """
    Extrae la fecha de cierre de campo.

    FIX v2: el año YA NO se infiere -- el archivo sí trae año explícito
    en cada fila (ej. ", 2025" / ", 2026"), simplemente no se estaba
    leyendo. También se corrige el caso de rangos de un solo mes tipo
    "Dec 7-11, 2025", donde el día final NO tiene mes propio: antes el
    regex encontraba solo "Dec 7" y perdía el "11".
    """
    if pd.isna(date_str):
        return pd.NaT
    s = str(date_str)
    s = re.sub(r'\[\d+\]', '', s)          # quita sufijos "[1]", "[2]"...
    # FIX v3: reemplaza "through" por un guion en vez de borrarlo -- borrarlo
    # podía, en teoría, fusionar dos fechas en una sola cadena ambigua.
    s = re.sub(r'\bthrough\b', '-', s, flags=re.IGNORECASE).strip()

    year_match = re.search(r'(\d{4})', s)   # año explícito en el string
    if not year_match:
        return pd.NaT
    year = year_match.group(1)

    # separar en tramo inicial / final del rango por el último guion
    pieces = re.split(r'\s*[-–—]\s*', s)
    last_piece = pieces[-1]

    month_pat = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})'
    m = re.search(month_pat, last_piece)
    if m:
        mon, day = m.group(1), m.group(2)
    else:
        # el día final no trae mes propio (ej. "Dec 7-11, 2025"):
        # se reutiliza el mes de la primera parte del rango.
        day_match = re.search(r'(\d{1,2})', last_piece)
        mon_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', s)
        if not (day_match and mon_match):
            return pd.NaT
        mon, day = mon_match.group(1), day_match.group(1)

    try:
        return pd.to_datetime(f"{mon} {day} {year}", format='%b %d %Y')
    except ValueError:
        return pd.NaT


def dedupe_poll_variants(df):
    """
    FIX v2: varias filas del Excel son variantes del MISMO campo de
    encuesta (mismo pollster + misma fecha) publicadas como (LV)/(RV)/(A)
    o como sub-muestras numeradas [1]/[2]/[3]. Tratarlas como encuestas
    independientes en el promedio ponderado infla artificialmente el
    peso de ese campo específico frente a un pollster que solo publicó
    una cifra. Regla explícita:
      - Si hay variante (LV): se usa esa (mejor proxy cerca de la
        elección).
      - Si no hay (LV) pero sí (RV): se usa esa.
      - Si son variantes sin etiqueta de tipo de votante (numeradas):
        se promedian en una sola observación equivalente.
    """
    df = df.copy()
    base = df['Poll_Source'].str.replace(r'\s*\((LV|RV|A)\)', '', regex=True, flags=re.IGNORECASE)
    base = base.str.replace(r'\s*\[\d+\]', '', regex=True).str.strip()
    is_lv = df['Poll_Source'].str.contains(r'\(LV\)', case=False, na=False)
    is_rv = df['Poll_Source'].str.contains(r'\(RV\)', case=False, na=False)

    df['_base_pollster'] = base
    df['_is_lv'] = is_lv
    df['_is_rv'] = is_rv

    kept_rows = []
    for (pollster, date), group in df.groupby(['_base_pollster', 'Date'], sort=False):
        if len(group) == 1:
            kept_rows.append(group.iloc[0])
            continue
        if group['_is_lv'].any():
            kept_rows.append(group[group['_is_lv']].iloc[0])
        elif group['_is_rv'].any():
            kept_rows.append(group[group['_is_rv']].iloc[0])
        else:
            avg_row = group.iloc[0].copy()
            for col in ['Donalds', 'Collins', 'Fishback', 'Renner', 'Other', 'Undecided']:
                if col in group.columns:
                    avg_row[col] = pd.to_numeric(group[col], errors='coerce').mean()
            kept_rows.append(avg_row)

    result = pd.DataFrame(kept_rows).drop(columns=['_base_pollster', '_is_lv', '_is_rv'])
    return result.reset_index(drop=True)


n_before = len(polls_rep)
polls_rep = dedupe_poll_variants(polls_rep)
print(f"Encuestas antes de deduplicar variantes LV/RV/sub-muestras: {n_before}")
print(f"Encuestas después (una observación por campo real):        {len(polls_rep)}")

polls_rep['Is_LV'] = polls_rep['Poll_Source'].str.contains(r'\(LV\)', na=False, flags=re.IGNORECASE)
polls_rep['Is_RV'] = polls_rep['Poll_Source'].str.contains(r'\(RV\)', na=False, flags=re.IGNORECASE)

# FIX v2: la columna Sample viene 100% vacía en este archivo (0/46 con
# dato real). Se marca explícitamente en vez de fingir que se conoce.
# Nota: como el valor imputado es la MISMA constante para todas las
# filas, no distorsiona el promedio ponderado entre sí (un factor común
# se cancela en np.average), pero si en el futuro se agregan encuestas
# con muestra real mezcladas con imputadas, esa comparación sí dejaría
# de ser neutral -- por eso queda la bandera.
polls_rep['Sample_Imputed'] = polls_rep['Sample'].isna()
polls_rep['Sample'] = pd.to_numeric(polls_rep['Sample'], errors='coerce').fillna(500)
if polls_rep['Sample_Imputed'].mean() > 0.5:
    print(f"⚠️ AVISO: {polls_rep['Sample_Imputed'].mean()*100:.0f}% de las encuestas no traen tamaño de "
          f"muestra real -- el término 'Sample' del ponderador NO está discriminando por calidad de muestra hoy.")

polls_rep['End_Date'] = polls_rep['Date'].apply(extract_end_date)
polls_rep['Days_Since_Poll'] = (TODAY - polls_rep['End_Date']).dt.days

assert polls_rep['End_Date'].notna().all(), "Quedan fechas sin parsear -- revisar formatos nuevos en Date."
assert (polls_rep['Days_Since_Poll'] >= 0).all(), \
    "Hay encuestas con fecha futura -- revisar columna Date."

# FIX: no descartar candidatos reales (Renner, Other). Antes se
# rellenaban con 0 incluso cuando el pollster simplemente no preguntó
# por ellos (NaN != 0). Ahora se suman solo los valores SÍ reportados
# (min_count=1 hace que una fila con AMBOS vacíos siga siendo NaN, no 0).
polls_rep['Renner'] = pd.to_numeric(polls_rep['Renner'], errors='coerce')
polls_rep['Other'] = pd.to_numeric(polls_rep['Other'], errors='coerce')
polls_rep['Undecided'] = pd.to_numeric(polls_rep['Undecided'], errors='coerce')
polls_rep['Other_Named_Total'] = polls_rep[['Renner', 'Other']].sum(axis=1, min_count=1)

print("Consolidando Voto Anticipado y Demográficos por Condado...")

ev_summary['Rep_Turnout_Pct'] = (ev_summary['Cast_Rep'] / ev_summary['Reg_Rep']) * 100
ev_summary['Dem_Turnout_Pct'] = (ev_summary['Cast_Dem'] / ev_summary['Reg_Dem']) * 100

cols_demograficas = [
    'County', 'Total population', 'White alone_x', 'Black or African American alone',
    'Hispanic or Latino Origin', 'Population 65 years and over',
    'Population 18 to 24 years', "Bachelor's degree or higher_1"
]
demo_subset = ev_demographics[cols_demograficas].copy()

demo_subset.rename(columns={
    'White alone_x': 'Pop_White',
    'Black or African American alone': 'Pop_Black',
    'Hispanic or Latino Origin': 'Pop_Hispanic',
    'Population 65 years and over': 'Pop_65_Plus',
    'Population 18 to 24 years': 'Pop_18_24',
    "Bachelor's degree or higher_1": 'Pop_Bachelors_Plus'
}, inplace=True)

# FIX v2: validate="one_to_one" hace explícito que esperamos exactamente
# un condado del padrón por cada condado demográfico/histórico -- si un
# futuro refresh de datos trae nombres desalineados (ej. "Miami Dade"
# vs "Miami-Dade"), esto truena en vez de fallar en silencio.
county_master = ev_summary[['County', 'Reg_Rep', 'Cast_Rep', 'Rep_Turnout_Pct']].merge(
    demo_subset, on='County', how='left', validate='one_to_one'
)

county_master = county_master.merge(
    turnout_hist[['County', 'Avg_Pct_Gov_Primaries', 'Pct_2022', 'Pct_2018', 'Diff_2022_vs_2018']],
    on='County', how='left', validate='one_to_one'
)

assert county_master['Pct_2018'].notna().all(), \
    "Hay condados sin match en el histórico de turnout -- revisar nombres de condado."

# FIX v3 (auditoría solicitada del histórico 2018/2022): se cruza el
# archivo de turnout externo (Turnout_by_County) contra el resultado
# que ESTE MISMO notebook calculó en la celda de "Extracción histórica"
# (Florida_Governor_Primarias_2018_2022.xlsx) para verificar, con datos
# propios y no solo con el mensaje impreso, que 2022 no es comparable a
# 2018 como referencia de turnout republicano.
try:
    hist_2018 = pd.read_excel('Florida_Governor_Primaries_2018_2022.xlsx', sheet_name='Governor_Primary_2018')
    hist_2022 = pd.read_excel('Florida_Governor_Primaries_2018_2022.xlsx', sheet_name='Governor_Primary_2022')

    rep_votes_2018 = hist_2018['Total_Rep_Votes'].sum()
    rep_votes_2022 = hist_2022['Total_Rep_Votes'].sum()

    audit_2018 = turnout_hist[['County', 'Turnout_2018']].merge(
        hist_2018[['County', 'Total_Primary_Votes']], on='County'
    )
    audit_2022 = turnout_hist[['County', 'Turnout_2022']].merge(
        hist_2022[['County', 'Total_Primary_Votes']], on='County'
    )
    # FIX v4 (punto #17 de la revisión): la razón estatal correcta es
    # suma(Turnout)/suma(Votos), no el promedio de razones por condado
    # (que pondera igual a un condado de 5,000 votantes que a uno de
    # 500,000). Se dejan ambas para transparencia.
    ratio_2018_mean_of_ratios = (audit_2018['Turnout_2018'] / audit_2018['Total_Primary_Votes']).mean()
    ratio_2022_mean_of_ratios = (audit_2022['Turnout_2022'] / audit_2022['Total_Primary_Votes']).mean()
    ratio_2018 = audit_2018['Turnout_2018'].sum() / audit_2018['Total_Primary_Votes'].sum()
    ratio_2022 = audit_2022['Turnout_2022'].sum() / audit_2022['Total_Primary_Votes'].sum()

    print("\n--- AUDITORÍA: ¿Turnout_by_County es consistente con la extracción histórica del notebook? ---")
    print(f"Votos totales REP primaria de gobernador, 2018 (todo el estado): {rep_votes_2018:,.0f}")
    print(f"Votos totales REP primaria de gobernador, 2022 (todo el estado): {rep_votes_2022:,.0f}")
    print(f"Turnout_2018 (participación general del día) / votos GOV totales 2018: {ratio_2018:.2f}x "
          f"(razón estatal correcta; promedio simple por condado: {ratio_2018_mean_of_ratios:.2f}x)")
    print(f"Turnout_2022 (participación general del día) / votos GOV totales 2022: {ratio_2022:.2f}x "
          f"(razón estatal correcta; promedio simple por condado: {ratio_2022_mean_of_ratios:.2f}x)")
    if rep_votes_2022 == 0:
        print("CONFIRMADO con datos propios del notebook: 0 votos republicanos en la primaria de "
              "gobernador 2022 en TODOS los condados -- no hubo contienda REP. Por eso Pct_2022 "
              "(participación general del día, dominada por la primaria DEM sí competitiva) NO es un "
              "proxy válido de comportamiento republicano en primaria disputada, y no se usa más abajo "
              "para el turnout esperado de 2026.")

    # FIX v4 (punto CRÍTICO #15/#16 de la revisión): falta demostrar si
    # Pct_2018 es una tasa REPUBLICANA o una tasa GENERAL (todos los
    # partidos). Se verifica cruzando Reg_2018 contra el padrón actual
    # (2026) desglosado por partido: si Reg_2018 se parece al padrón
    # TOTAL de 2026 (todos los partidos), es una tasa general: si se
    # pareciera solo al padrón republicano, sería una tasa REP.
    reg_check = ev_summary[['County', 'Reg_Total', 'Reg_Rep']].merge(
        turnout_hist[['County', 'Reg_2018']], on='County', validate='one_to_one'
    )
    corr_vs_total = reg_check['Reg_2018'].corr(reg_check['Reg_Total'])
    corr_vs_rep = reg_check['Reg_2018'].corr(reg_check['Reg_Rep'])
    ratio_vs_total = (reg_check['Reg_2018'] / reg_check['Reg_Total']).mean()
    ratio_vs_rep = (reg_check['Reg_2018'] / reg_check['Reg_Rep']).mean()
    print(f"\n¿Reg_2018 es un padrón republicano o general? Reg_2018 correlaciona {corr_vs_total:.3f} con "
          f"el padrón TOTAL 2026 (Reg_2018 ≈ {ratio_vs_total*100:.0f}% del padrón total actual) vs. "
          f"{corr_vs_rep:.3f} con el padrón SOLO-REP 2026 (Reg_2018 ≈ {ratio_vs_rep*100:.0f}% de eso, "
          f"es decir ~2x más grande que el padrón republicano solo).")
    print("CONCLUSIÓN: Reg_2018/Pct_2018 son cifras de TODOS los partidos, no específicas de republicanos. "
          "'total_expected_turnout' de más abajo asume que los republicanos participan a la misma TASA "
          "que el electorado general en 2018 -- un supuesto adicional, no verificado con estos archivos "
          "(no hay padrón/turnout histórico desglosado por partido disponible en esta carpeta).")
except FileNotFoundError:
    print("\n(No se encontró Florida_Governor_Primaries_2018_2022.xlsx en esta carpeta -- se omite la "
          "auditoría cruzada 2018/2022; se asume sin verificar que Pct_2018/Pct_2022 son comparables.)")

print("\n--- RESUMEN DE DATOS LIMPIOS ---")
print(f"Encuestas procesadas: {len(polls_rep)}")
print(f"Rango de fechas de encuestas: {polls_rep['End_Date'].min().strftime('%Y-%m-%d')} a {polls_rep['End_Date'].max().strftime('%Y-%m-%d')}")
print(f"Condados consolidados: {len(county_master)}")
print("\nMuestra de la base consolidada por condado (Top 3 por Voto Anticipado Rep):")
print(county_master.sort_values(by='Cast_Rep', ascending=False)[['County', 'Reg_Rep', 'Cast_Rep', 'Rep_Turnout_Pct', 'Pop_65_Plus']].head(3))


# =====================================================================
# CELDA "2. Ponderación" -- CORREGIDA v2
# =====================================================================
print("\nCalculando promedios ponderados de encuestas (Time-Decay & House Effects)...")

house_effects = {
    'Targoz Market Research': {'Donalds': 1.5, 'Collins': -0.5},
    'Change Research (D)': {'Donalds': -2.0, 'Collins': 1.0},
    'RealClearPolitics': {'Donalds': 0.0, 'Collins': 0.0},
}


def clean_pollster_name(pollster):
    """
    FIX v2: antes se hacía pollster.split('(')[0], lo que convertía
    "Change Research (D)" en "Change Research" -- y esa llave nunca
    existía en house_effects, así que el ajuste de esa encuestadora
    JAMÁS se aplicaba. Ahora solo se eliminan las etiquetas de tipo de
    votante (LV)/(RV), que no forman parte del nombre de la
    encuestadora; los sufijos de patrocinio partidista como (D)/(R) se
    conservan porque sí identifican a la encuestadora para el cruce
    contra house_effects.
    """
    name = re.sub(r'\s*\((LV|RV)\)', '', pollster, flags=re.IGNORECASE)
    name = re.sub(r'\s*\[\d+\]', '', name)
    return name.strip()


def apply_house_effects(row, candidate, effects_dict):
    pollster = row['Poll_Source']
    base_val = row[candidate]
    if pd.isna(base_val):
        return np.nan
    pollster_clean = clean_pollster_name(pollster)
    bias = effects_dict.get(pollster_clean, {}).get(candidate, 0.0)
    return base_val - bias


for cand in ['Donalds', 'Collins', 'Fishback']:
    if cand in polls_rep.columns:
        polls_rep[f'{cand}_Adj'] = polls_rep.apply(lambda r: apply_house_effects(r, cand, house_effects), axis=1)

# Verificación explícita de que el house effect de Change Research (D)
# sí se está aplicando (antes se aplicaba a 0 filas).
cr_mask = polls_rep['Poll_Source'].apply(clean_pollster_name) == 'Change Research (D)'
cr_shift = (polls_rep.loc[cr_mask, 'Donalds'] - polls_rep.loc[cr_mask, 'Donalds_Adj'])
print(f"Filas de 'Change Research (D)' con house effect aplicado: {(cr_shift != 0).sum()} / {cr_mask.sum()}")

half_life = 14
decay_rate = np.log(2) / half_life
polls_rep['Poll_Weight'] = polls_rep['Sample'] * np.exp(-decay_rate * polls_rep['Days_Since_Poll'])


def weighted_average(df, value_col, weight_col):
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    return np.average(subset[value_col], weights=subset[weight_col])


def poll_dispersion(df, value_col, weight_col, mean_val_pct):
    """
    Dispersión ponderada ENTRE encuestas (proxy conservador).
    OJO: esto mide qué tan distintas son las encuestas entre sí, NO es
    un error estándar calibrado del promedio agregado (para eso haría
    falta un modelo jerárquico con house-effects y correlación entre
    encuestas -- ver nota en la celda de Ensemble). Se usa como
    aproximación razonable para un prototipo, no como SE certificado.
    """
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    variance = np.average((subset[value_col] - mean_val_pct) ** 2, weights=subset[weight_col])
    return np.sqrt(variance)


def fit_renner_split_beta(paired_df):
    """
    FIX v6 (bug #15 de la revisión más reciente): esta lógica vivía
    hardcodeada UNA sola vez en la celda de Ponderación, usando SIEMPRE
    el polls_rep/Poll_Weight globales -- así que cuando
    recompute_and_simulate() recalculaba Poll_Weight con un half_life
    distinto, el split Renner/Other seguía usando la Beta ajustada con el
    half_life BASE (inconsistencia detectada por el usuario: "half_life=7
    recalcula Other_Named con nuevos pesos, pero no recalcula
    completamente la composición interna Renner/Other con esos mismos
    nuevos pesos"). Se extrae a función para poder llamarla también desde
    recompute_and_simulate() sobre el DataFrame recalculado.
    Devuelve (frac, alpha, beta, kappa, n_pareadas).

    FIX v7 (bug matemático nuevo señalado en la revisión más reciente): la
    media se calcula como ratio de SUMAS ponderadas,
        frac = (sum_i w_i R_i) / (sum_i w_i (R_i+O_i)),
    que es ALGEBRAICAMENTE equivalente a una media ponderada de los
    ratios individuales r_i = R_i/(R_i+O_i) usando pesos EFECTIVOS
    w_i*(R_i+O_i) -- no los w_i (Poll_Weight) crudos:
        frac = sum_i [w_i*(R_i+O_i)] * r_i / sum_i [w_i*(R_i+O_i)].
    La varianza de esos mismos ratios, para ser consistente con la MISMA
    media, debe usar esos mismos pesos efectivos. Antes se usaba
    Poll_Weight crudo para la varianza -- una encuesta con Renner+Other
    grande (más "masa" de esa categoría en esa encuesta) pesaba menos de
    lo que le correspondía frente al estimador de la media, subestimando
    o distorsionando la precisión implícita (kappa).
    """
    paired_df = paired_df.dropna(subset=['Renner', 'Other']).copy()
    if paired_df.empty:
        return 0.5, 1.5, 1.5, 3.0, 0

    renner_paired_avg = np.average(paired_df['Renner'], weights=paired_df['Poll_Weight'])
    other_paired_avg = np.average(paired_df['Other'], weights=paired_df['Poll_Weight'])
    frac = renner_paired_avg / (renner_paired_avg + other_paired_avg)

    if len(paired_df) > 1:
        paired_df['Renner_Frac'] = paired_df['Renner'] / (paired_df['Renner'] + paired_df['Other'])
        # Pesos EFECTIVOS w_i*(R_i+O_i) -- mismos que hacen que la media
        # ponderada de Renner_Frac reproduzca exactamente `frac` de arriba.
        paired_df['_Effective_Weight'] = paired_df['Poll_Weight'] * (paired_df['Renner'] + paired_df['Other'])
        var = np.average((paired_df['Renner_Frac'] - frac) ** 2, weights=paired_df['_Effective_Weight'])
    else:
        var = np.nan

    max_var = frac * (1 - frac) * 0.999
    if not np.isfinite(var) or var <= 0:
        kappa = 3.0  # sin info suficiente -> Beta muy dispersa (poca confianza)
    else:
        var = min(var, max_var)
        kappa = max(frac * (1 - frac) / var - 1, 3.0)
    alpha = frac * kappa
    beta = (1 - frac) * kappa
    return frac, alpha, beta, kappa, len(paired_df)


current_polling_avg = {}
current_polling_std = {}
for cand in ['Donalds', 'Collins', 'Fishback']:
    mean_pct = weighted_average(polls_rep, f'{cand}_Adj', 'Poll_Weight')
    std_pct = poll_dispersion(polls_rep, f'{cand}_Adj', 'Poll_Weight', mean_pct)
    current_polling_avg[cand] = mean_pct / 100.0
    current_polling_std[cand] = std_pct / 100.0

# FIX v2 (punto crítico #4 de la revisión): la columna Undecided SÍ
# existe y SÍ se reporta en el 100% de las encuestas -- se usa
# directamente en vez de inferir el pool de indecisos como un residuo
# artificial que "cierra" la suma a 100%.
current_undecided_avg = weighted_average(polls_rep, 'Undecided', 'Poll_Weight') / 100.0
undecided_std = poll_dispersion(polls_rep, 'Undecided', 'Poll_Weight', current_undecided_avg * 100) / 100.0

# FIX v4 (punto CRÍTICO #6/#7/#9 de la revisión): en v3 se calculaban
# renner_avg y other_avg por separado, cada uno con dropna() sobre SU
# PROPIA columna -- Renner se reportó en 33/39 encuestas y Other en
# solo 11/39, y NO son las mismas encuestas. Por construcción
# renner_avg + other_avg != other_named_avg (verificado: 5.56 + 4.39 =
# 9.95%, contra 7.25% de Other_Named_Total calculado sobre encuestas
# consistentes). Esa mezcla de magnitudes de muestras distintas es la
# causa de que la tabla de sensibilidad sumara 101.6% en vez de 100%.
# FIX: Other_Named_Total (una sola columna, consistente por poll) es la
# única cantidad que entra a la composición del modelo. La partición
# Renner/Other_Residual se estima SOLO al final, como una fracción
# aparte, usando únicamente las encuestas donde AMBAS columnas se
# reportan (comparación pareada, sin mezclar muestras distintas).
paired_renner_other = polls_rep.dropna(subset=['Renner', 'Other']).copy()

# FIX v5 (punto #5 de la revisión): renner_split_frac se usaba como un
# valor FIJO (determinístico) dentro del Monte Carlo, pese a estar
# estimado sobre solo 10 encuestas -- se reemplaza por una Beta(a,b)
# calibrada por método de momentos: media = ratio de sumas ponderadas,
# varianza = dispersión ENTRE encuestas de la fracción Renner/(Renner+Other)
# de cada poll individual. Con solo 10 encuestas la varianza es ruidosa,
# así que se acota con un kappa mínimo de 3 ("muy poca información").
# FIX v6 (bug #15): esto ahora vive en fit_renner_split_beta() (función
# reutilizable) para que recompute_and_simulate() pueda recalcularlo con
# el half_life alternativo, en vez de reusar siempre la Beta del modelo
# base -- ver esa función más abajo.
renner_split_frac, renner_split_alpha, renner_split_beta, renner_split_kappa, _n_paired = \
    fit_renner_split_beta(paired_renner_other)
print(f"Fracción Renner dentro de 'Other_Named' (solo {_n_paired} encuestas que reportan "
      f"AMBAS columnas, para no mezclar muestras distintas): {renner_split_frac*100:.1f}%")
print(f"Beta(a={renner_split_alpha:.2f}, b={renner_split_beta:.2f}) para simular el split Renner/Other "
      f"(kappa implícito={renner_split_kappa:.1f}, sobre {_n_paired} encuestas pareadas) -- "
      f"reemplaza el punto fijo {renner_split_frac*100:.1f}% en el Monte Carlo.")

# FIX v5 (punto CRÍTICO #1 de la revisión más reciente): Other_Named_Total
# se construía con sum(axis=1, min_count=1) sobre TODAS las 39 encuestas.
# Esa función solo evita "0+0=NaN"; NO evita "6+NaN=6". Una encuesta que
# reporta Renner=6 y deja Other en blanco entraba como Other_Named_Total=6,
# es decir, tratando el componente faltante (Other) como cero -- exactamente
# el mismo error de "NaN != 0" que ya se había corregido para Renner/Other
# por separado más arriba, pero reintroducido aquí al combinarlas.
# Verificado numéricamente: sobre las 39 encuestas (min_count=1) el
# promedio ponderado da 7.25%; restringido a las 10 encuestas que
# reportan AMBAS columnas (mismo subconjunto que ya se usaba para
# renner_split_frac) da 9.21% (± 1.15 pts) -- una diferencia de ~2 pts
# (~27% relativa), nada despreciable. Se pierden observaciones (10 de 39,
# ~34.6% del peso total por decaimiento temporal, dominado por las
# encuestas más recientes -- ver diagnóstico), pero es la única forma de
# no mezclar "solo Renner" con "Renner+Other" bajo una etiqueta que se
# trata como una sola cantidad consistente en el resto del pipeline.
if not paired_renner_other.empty:
    other_named_avg = weighted_average(paired_renner_other, 'Other_Named_Total', 'Poll_Weight') / 100.0
    other_named_std = poll_dispersion(paired_renner_other, 'Other_Named_Total', 'Poll_Weight', other_named_avg * 100) / 100.0
else:
    # Fallback (no debería ocurrir con los datos actuales): sin encuestas
    # pareadas no hay forma consistente de estimar Other_Named_Total, así
    # que se recurre al total sobre min_count=1 con una advertencia.
    print("⚠️ AVISO: no hay encuestas con Renner y Other reportados simultáneamente -- "
          "Other_Named_Total se aproxima con min_count=1 (menos confiable).")
    other_named_avg = weighted_average(polls_rep, 'Other_Named_Total', 'Poll_Weight') / 100.0
    other_named_std = poll_dispersion(polls_rep, 'Other_Named_Total', 'Poll_Weight', other_named_avg * 100) / 100.0
print(f"Other_Named_Total recalculado SOLO sobre las {len(paired_renner_other)} encuestas que reportan "
      f"ambas columnas (antes: 7.25% sobre min_count=1 de 39 encuestas, mezclando 'solo Renner' con "
      f"'Renner+Other'): {other_named_avg*100:.2f}% (± {other_named_std*100:.2f} pts)")

print("\nPromedio Ponderado Actual (Ajustado, fechas y house effects corregidos):")
for k, v in current_polling_avg.items():
    print(f"{k}: {v*100:.2f}% (dispersión entre encuestas: {current_polling_std[k]*100:.2f} pts)")
print(f"Otros candidatos con nombre (Renner + Other, solo encuestas que los reportan): {other_named_avg*100:.2f}%")
print(f"Indecisos reportados directamente por las encuestas (columna Undecided): {current_undecided_avg*100:.2f}%")

# =======================================================================
# APÉNDICE / DEMO -- IPF / Raking sobre datos SINTÉTICOS
# NO forma parte del forecast efectivo: no corrige polls_rep, no alimenta
# el Ensemble ni el Monte Carlo. Se conserva únicamente para ilustrar que
# el algoritmo de raking (especialidad del usuario) está correctamente
# implementado, a la espera de microdatos demográficos reales de la
# encuesta -- que hoy NO existen en la carpeta de datos. FIX v7 (punto
# menor #2 de la revisión más reciente): se refuerza esta separación
# visual para que no se confunda con parte del forecast si el notebook
# se publica como proyecto.
# =======================================================================
print("\n" + "=" * 70)
print("[APÉNDICE/DEMO -- NO ES PARTE DEL FORECAST] IPF sobre muestra SINTÉTICA")
print("(no corrige polls_rep, no alimenta el Ensemble ni el Monte Carlo)")
print("=" * 70)

targets = {
    'Age_Group': {'18_44': 0.20, '45_64': 0.35, '65_Plus': 0.45},
    'Race': {'White': 0.82, 'Hispanic': 0.12, 'Black': 0.03, 'Other': 0.03}
}

np.random.seed(42)
sample_size = 800
mock_survey = pd.DataFrame({
    'Respondent_ID': range(1, sample_size + 1),
    'Age_Group': np.random.choice(['18_44', '45_64', '65_Plus'], p=[0.25, 0.40, 0.35], size=sample_size),
    'Race': np.random.choice(['White', 'Hispanic', 'Black', 'Other'], p=[0.75, 0.15, 0.05, 0.05], size=sample_size),
    'Base_Weight': 1.0
})


def rake_survey(df, targets, weight_col='Weight', max_iterations=20, tolerance=0.001):
    df = df.copy()
    if weight_col not in df.columns:
        df[weight_col] = df['Base_Weight']

    for iteration in range(max_iterations):
        max_diff = 0
        for category, target_dist in targets.items():
            current_dist = df.groupby(category)[weight_col].sum() / df[weight_col].sum()
            adjustment_factors = {level: target_dist[level] / current_dist.get(level, 1)
                                   for level in target_dist.keys()}
            df['temp_adj'] = df[category].map(adjustment_factors)
            df[weight_col] = df[weight_col] * df['temp_adj']
            diff = max(abs(current_dist.get(k, 0) - v) for k, v in target_dist.items())
            max_diff = max(max_diff, diff)

        df.drop(columns=['temp_adj'], inplace=True)
        if max_diff < tolerance:
            print(f"Convergencia alcanzada en la iteración {iteration + 1}.")
            break

    return df


survey_weighted = rake_survey(mock_survey, targets, weight_col='Final_Weight')

print("\nMárgenes demográficos tras IPF (Raza) -- SOLO sobre la muestra sintética:")
final_margins_race = survey_weighted.groupby('Race')['Final_Weight'].sum() / survey_weighted['Final_Weight'].sum()
print((final_margins_race.round(4) * 100))
print("=" * 70)
print("[FIN DEL APÉNDICE/DEMO] -- lo que sigue (Ensamble Bayesiano) SÍ usa datos reales.")
print("=" * 70)


# =====================================================================
# CELDA "3. Modelado Ensemble" -- CORREGIDA v2
# =====================================================================
print("\nIniciando Ensamble Bayesiano: Fundamentales + Encuestas...")

# FIX v2 (punto #11 de la revisión): renombrado de fundamentals_priors a
# subjective_priors. No son fundamentales estimados (2018/2022,
# demografía, fundraising, endorsements, name recognition...), son
# supuestos subjetivos de partida. Se mantienen los mismos valores
# porque no hay todavía un procedimiento reproducible que los calcule;
# el nombre ya no promete más de lo que el dato entrega.
subjective_priors = {
    'Donalds': {'mean': 0.45, 'std': 0.08},
    'Collins': {'mean': 0.15, 'std': 0.05},
    'Fishback': {'mean': 0.10, 'std': 0.04}
}

polling_data = {
    cand: {'mean': current_polling_avg[cand], 'std': current_polling_std[cand]}
    for cand in subjective_priors.keys()
}


def bayesian_update(prior_mean, prior_std, data_mean, data_std):
    """
    NOTA (punto #12 de la revisión): esto actualiza cada candidato como
    una Normal INDEPENDIENTE. En una elección real p_D + p_C + p_F +
    p_otros = 1, así que si Donalds sube alguien más necesariamente baja
    -- esta dependencia no está modelada aquí. Para un prototipo es
    aceptable (la restricción de suma sí se aplica más abajo al fijar
    final_ensemble_estimates y, sobre todo, en el paso Dirichlet de
    Monte Carlo). Para probabilidades calibradas de producción, esto
    debería ser una logistic-normal multivariada o un Dirichlet-
    multinomial en vez de 3 Normales independientes.
    """
    prior_precision = 1.0 / (prior_std ** 2)
    data_precision = 1.0 / (data_std ** 2)
    posterior_precision = prior_precision + data_precision
    posterior_mean = ((prior_mean * prior_precision) + (data_mean * data_precision)) / posterior_precision
    posterior_std = np.sqrt(1.0 / posterior_precision)
    return posterior_mean, posterior_std


ensemble_posteriors = {}
for candidate in subjective_priors.keys():
    p_mean = subjective_priors[candidate]['mean']
    p_std = subjective_priors[candidate]['std']
    d_mean = polling_data[candidate]['mean']
    d_std = polling_data[candidate]['std']
    post_mean, post_std = bayesian_update(p_mean, p_std, d_mean, d_std)
    ensemble_posteriors[candidate] = {'mean': post_mean, 'std': post_std}

total_assigned = sum(v['mean'] for v in ensemble_posteriors.values())

# FIX v2 (punto CRÍTICO #4 de la revisión): se usa el indeciso REAL
# reportado por las encuestas (current_undecided_avg) en vez de un
# residuo "lo que falte para sumar 100%". Se imprime también el residuo
# ingenuo como diagnóstico de consistencia -- si ambos difieren mucho,
# es señal de que el Bayes movió las medias lejos de lo que las
# encuestas muestran en crudo.
undecided_pool = current_undecided_avg
naive_residual_pool = max(1.0 - total_assigned - other_named_avg, 0.0)
closure_gap = undecided_pool - naive_residual_pool

print(f"Pool de Indecisos (dato REAL de la columna Undecided): {undecided_pool * 100:.2f}%")
print(f"  (vs. residuo ingenuo 1 - candidatos - otros: {naive_residual_pool * 100:.2f}% "
      f"| brecha de consistencia Bayes-vs-encuestas: {closure_gap * 100:+.2f} pts)\n")

undecided_allocation = {
    'Donalds': 0.60,
    'Collins': 0.25,
    'Fishback': 0.15
}

final_ensemble_estimates = {}
print("Resultados del Modelo Ensemble (Capa 1 + Capa 2 + Indecisos):")
print("-" * 60)
for candidate, post in ensemble_posteriors.items():
    final_mean = post['mean'] + (undecided_pool * undecided_allocation[candidate])
    final_ensemble_estimates[candidate] = {
        'mean': final_mean,
        'std': post['std']
    }
    # FIX v7 (punto #4 de la revisión más reciente): "Ensemble Final ±
    # std" mezclaba dos cosas de origen distinto -- final_mean YA incluye
    # la asignación puntual de indecisos, pero post['std'] es el std del
    # POSTERIOR ANTERIOR a esa asignación (y anterior también a la
    # incertidumbre de early vote/turnout/composición que sí modela el
    # Monte Carlo). Mostrarlos juntos como "± X%" sugiere que ese es el
    # intervalo de incertidumbre final del candidato, cuando NO lo es --
    # el intervalo correcto está más abajo (Mediana + IC95% del Monte
    # Carlo). Se relabela como "point estimate" y se remite explícitamente
    # a esa sección para la incertidumbre.
    print(f"{candidate}:")
    print(f"  └─ Priors subjetivos:     {subjective_priors[candidate]['mean']*100:.1f}%")
    print(f"  └─ Encuestas (Data):      {polling_data[candidate]['mean']*100:.1f}%")
    print(f"  └─ Point estimate (previo a Monte Carlo, incluye asignación puntual de indecisos): "
          f"{final_mean*100:.1f}% (std posterior pre-indecisos, NO es la incertidumbre final: {post['std']*100:.1f} pts "
          f"-- ver 'RANGOS PROBABLES DE VOTO' más abajo para el IC95% real)")


# =====================================================================
# CELDA "4. Simulación" -- CORREGIDA v4
# =====================================================================
import numpy as np
import pandas as pd

print("\nEjecutando Simulación Monte Carlo (10,000 iteraciones)...")

total_early_votes = float(
    ev_statewide.loc[ev_statewide['Metric'] == 'Already Cast - Republican', 'Value'].iloc[0]
)

total_expected_turnout = float(
    (county_master['Reg_Rep'] * county_master['Pct_2018'] / 100.0).sum()
)

# [Diagnóstico de la fórmula de varianza ponderada, corregida -- NO se
# usa como CV del modelo porque 2022 no es comparable, ver celda 1]
weighted_mean_diff = np.average(county_master['Diff_2022_vs_2018'], weights=county_master['Reg_Rep'])
weighted_var_diff = np.average(
    (county_master['Diff_2022_vs_2018'] - weighted_mean_diff) ** 2,
    weights=county_master['Reg_Rep']
)
turnout_swing_std_pts_fixed = np.sqrt(weighted_var_diff)
print(f"[Diagnóstico, NO USADO] std ponderado (fórmula corregida) del swing 2022 vs 2018: "
      f"{turnout_swing_std_pts_fixed:.2f} pts -- se descarta como base del CV porque 2022 no es un "
      f"punto de comparación válido para una primaria REP disputada (ver auditoría celda 1).")

TURNOUT_CV_ASSUMED = 0.12  # hiperparámetro asumido, NO calibrado con estos datos ni con literatura verificable
ensemble_estimates = final_ensemble_estimates

early_vote_point_shares = {
    'Donalds': ensemble_estimates['Donalds']['mean'],
    'Collins': ensemble_estimates['Collins']['mean'],
    'Fishback': ensemble_estimates['Fishback']['mean'],
}
EARLY_VOTE_CONFIDENCE = 25          # hiperparámetro asumido
UNDECIDED_ALLOCATION_CONFIDENCE = 20  # hiperparámetro asumido
undecided_allocation_point = {'Donalds': 0.60, 'Collins': 0.25, 'Fishback': 0.15}

remaining_votes_preview = total_expected_turnout - total_early_votes
print(f"Votos Esperados (Reg_Rep x Pct_2018): {total_expected_turnout:,.0f}")
print(f"Votos Emitidos (Early, dato real Statewide_Totals): {total_early_votes:,.0f} "
      f"({total_early_votes/total_expected_turnout*100:.1f}%)")
print(f"Votos Pendientes (Día de Elección, estimado): {remaining_votes_preview:,.0f} "
      f"({(1 - total_early_votes/total_expected_turnout)*100:.1f}%)\n")

early_vote_others_share = max(1.0 - sum(early_vote_point_shares.values()), 0.0)
print(f"Prior de Early Vote (centrado en el ensemble general): "
      f"Donalds {early_vote_point_shares['Donalds']*100:.1f}%, "
      f"Collins {early_vote_point_shares['Collins']*100:.1f}%, "
      f"Fishback {early_vote_point_shares['Fishback']*100:.1f}%, "
      f"Otros {early_vote_others_share*100:.1f}%")


def run_monte_carlo(early_confidence, undecided_confidence, turnout_cv_value, n_simulations=10_000, seed=42,
                     verbose=False, ensemble_posteriors_ov=None, other_named_avg_ov=None, other_named_std_ov=None,
                     undecided_avg_ov=None, undecided_std_ov=None, undecided_allocation_ov=None,
                     early_vote_point_shares_ov=None, early_vote_others_share_ov=None,
                     renner_split_alpha_ov=None, renner_split_beta_ov=None):
    """
    FIX v5 (punto #6 de la revisión más reciente): se agregan parámetros
    _ov (override) opcionales -- si se dejan en None, la función usa
    exactamente las mismas variables globales de siempre (comportamiento
    IDÉNTICO al usado en la celda de sensibilidad de EARLY_VOTE_CONFIDENCE
    / UNDECIDED_ALLOCATION_CONFIDENCE / TURNOUT_CV_ASSUMED). Cuando SÍ se
    pasan, permiten correr el Monte Carlo bajo un ensemble recalculado con
    otro half_life, otros house effects, u otros subjective_priors -- ver
    recompute_and_simulate() más abajo, usado en la sensibilidad de
    hiperparámetros "estructurales" (no solo de confianza/dispersión).
    Simulación Monte Carlo del resultado de la primaria, parametrizada
    por los 3 hiperparámetros que hoy son supuestos (no calibrados):
    EARLY_VOTE_CONFIDENCE, UNDECIDED_ALLOCATION_CONFIDENCE, TURNOUT_CV.
    Se refactorizó a función (FIX v4, punto #19 de la revisión) para
    poder correr el análisis de sensibilidad de la celda 6 sin duplicar
    la lógica.

    FIX v4 (puntos CRÍTICOS #11/#12/#13 de la revisión): antes se usaba
    una sola Dirichlet de 6 categorías (Donalds/Collins/Fishback/Renner/
    Other/Undecided) con un único kappa compartido -- pero las kappa
    implícitas por categoría iban de 23.9 (Undecided) a 871.1 (Other),
    una dispersión de ~36x. Una Dirichlet estándar SOLO tiene un
    parámetro de concentración total (kappa = suma de alphas), así que
    ninguna elección de alphas puede reproducir simultáneamente
    varianzas tan distintas por categoría -- forzarlo a una sola kappa
    (mediana) infla la varianza de categorías de alta confianza (Other)
    hasta ~3x y comprime la de categorías de baja confianza (Undecided,
    Renner) hasta ~50%.
    Fix aplicado ahora (sin llegar todavía a una logistic-normal
    multivariada, que sería el rediseño completo): se separa en DOS
    niveles de Dirichlet ("Dirichlet tree"), cada uno con su propio
    kappa, de forma que cada nivel agrupa categorías con kappas
    implícitas mucho más parecidas entre sí:
      Nivel 1 (kappa_top):    [Pool_Candidatos, Other_Named, Undecided]
      Nivel 2 (kappa_within): [Donalds, Collins, Fishback] DENTRO del pool
    Donalds/Collins/Fishback entre sí tienen kappas de 76.9-121.3 (~1.6x
    de spread) -- mucho más homogéneo que meterlos en el mismo balde que
    Other (871) o Undecided (23.9).
    """
    rng = np.random.default_rng(seed)

    # Resolución de overrides -> si no se pasó nada, se comporta exactamente
    # como antes (usa las variables globales del modelo base).
    ens_post = ensemble_posteriors_ov if ensemble_posteriors_ov is not None else ensemble_posteriors
    o_avg = other_named_avg_ov if other_named_avg_ov is not None else other_named_avg
    o_std = other_named_std_ov if other_named_std_ov is not None else other_named_std
    u_avg = undecided_avg_ov if undecided_avg_ov is not None else current_undecided_avg
    u_std = undecided_std_ov if undecided_std_ov is not None else undecided_std
    u_alloc = undecided_allocation_ov if undecided_allocation_ov is not None else undecided_allocation_point
    ev_shares = early_vote_point_shares_ov if early_vote_point_shares_ov is not None else early_vote_point_shares
    ev_others = early_vote_others_share_ov if early_vote_others_share_ov is not None else early_vote_others_share
    r_alpha = renner_split_alpha_ov if renner_split_alpha_ov is not None else renner_split_alpha
    r_beta = renner_split_beta_ov if renner_split_beta_ov is not None else renner_split_beta

    pool_mean = (ens_post['Donalds']['mean'] + ens_post['Collins']['mean']
                 + ens_post['Fishback']['mean'])
    # Varianza del pool asumiendo independencia entre candidatos -- la
    # MISMA simplificación ya documentada en la celda de Ensemble
    # (bayesian_update trata a cada candidato como Normal independiente).
    pool_var = (ens_post['Donalds']['std'] ** 2 + ens_post['Collins']['std'] ** 2
                + ens_post['Fishback']['std'] ** 2)
    pool_std = np.sqrt(pool_var)

    # FIX v6 (punto CRÍTICO #6 de la revisión más reciente): la Dirichlet
    # de 3 categorías [Pool, Other_Named, Undecided] volvió a sufrir el
    # mismo problema que el árbol de 2 niveles quería resolver. Tras
    # corregir Other_Named (FIX v5), sus kappas implícitas quedaron en
    # Pool=46.3, Other_Named=614.4, Undecided=24.0 -- ~25.6x de spread.
    # Una Dirichlet de 3 categorías SOLO tiene una concentración total
    # compartida, así que kappa_top=mediana=46.3 seguía inflando la
    # varianza simulada de Other_Named (~3.6x de más) y comprimiendo la de
    # Undecided (~27% de menos) -- exactamente el defecto que el árbol
    # pretendía resolver, reaparecido un nivel más arriba.
    # FIX: se profundiza el árbol a splits BINARIOS. Una Beta (Dirichlet
    # de 2 categorías) SÍ tiene un grado de libertad de forma libre por
    # split, así que cada nivel usa la kappa que le corresponde SIN
    # comprometerla con categorías de escala distinta. FIX v7 (punto #3 de
    # la revisión más reciente): "Beta exacta" era una etiqueta demasiado
    # fuerte -- lo que se hace es un ajuste por MOMENTOS (method-of-
    # moments): se elige la Beta cuya media y varianza COINCIDEN con la
    # media/varianza estimadas de los datos, pero esas media/varianza en
    # sí son aproximaciones (ver Nivel 1 más abajo: se ignora la
    # randomness del denominador). Es "exacta" respecto a la aproximación
    # elegida, no respecto al proceso electoral real -- se renombra en
    # todo el notebook a "Beta moment-matched".
    #   Nivel 0 (Beta moment-matched): Undecided        vs Decided
    #   Nivel 1 (Beta moment-matched): Other_Named      vs Pool_Candidatos   (dentro de Decided)
    #   Nivel 2 (Dirichlet):           Donalds/Collins/Fishback              (dentro de Pool, 3-way,
    #                                  homogéneo: kappas 76.9-121.3, ~1.6x -- se mantiene igual que v4/v5)
    #   Nivel 3 (Beta moment-matched): Renner           vs Other_Residual    (dentro de Other_Named, FIX v5)

    # --- Nivel 0: Undecided vs. Decided ---
    kappa_ud = max(u_avg * (1 - u_avg) / (u_std ** 2) - 1, 1.0)
    alpha_ud, beta_ud = u_avg * kappa_ud, (1 - u_avg) * kappa_ud
    S_undecided = rng.beta(alpha_ud, beta_ud, size=n_simulations)
    S_decided = 1.0 - S_undecided

    # --- Nivel 1: Other_Named vs. Pool_Candidatos (dentro de Decided) ---
    # Aproximación (misma ya usada y documentada en Nivel 2 D/C/F): se
    # escala la std de Other_Named por el mismo denominador (pool_mean +
    # o_avg) que su media -- asume que la varianza del denominador es
    # secundaria frente a la del numerador; NO modela la randomness propia
    # del denominador (limitación ya señalada por el usuario para el
    # cociente D/Pool, aquí es la misma simplificación -- por eso es
    # "moment-matched", no "exacta").
    decided_scale = pool_mean + o_avg
    p_other_within_decided = o_avg / decided_scale
    std_other_within_decided = o_std / decided_scale
    kappa_od = max(
        p_other_within_decided * (1 - p_other_within_decided) / (std_other_within_decided ** 2) - 1, 1.0
    )
    alpha_od = p_other_within_decided * kappa_od
    beta_od = (1 - p_other_within_decided) * kappa_od
    within_decided_split = rng.beta(alpha_od, beta_od, size=n_simulations)
    S_other = S_decided * within_decided_split
    S_pool = S_decided * (1 - within_decided_split)

    # --- Nivel 2: reparto DENTRO del pool (Donalds/Collins/Fishback) ---
    within_means_raw = np.array([
        ens_post['Donalds']['mean'],
        ens_post['Collins']['mean'],
        ens_post['Fishback']['mean'],
    ]) / pool_mean
    within_stds_raw = np.array([
        ens_post['Donalds']['std'],
        ens_post['Collins']['std'],
        ens_post['Fishback']['std'],
    ]) / pool_mean
    within_kappas = (within_means_raw * (1 - within_means_raw)) / (within_stds_raw ** 2) - 1
    kappa_within = max(np.median(within_kappas), 1.0)
    within_alphas = np.clip(within_means_raw * kappa_within, 1e-3, None)

    simulated_within = rng.dirichlet(within_alphas, size=n_simulations)

    remaining_donalds_base = S_pool * simulated_within[:, 0]
    remaining_collins_base = S_pool * simulated_within[:, 1]
    remaining_fishback_base = S_pool * simulated_within[:, 2]

    # --- Reparto de indecisos (su propia Dirichlet, su propio kappa) ---
    undecided_alloc_alpha = [u_alloc[c] * undecided_confidence
                              for c in ['Donalds', 'Collins', 'Fishback']]
    simulated_undecided_alloc = rng.dirichlet(undecided_alloc_alpha, size=n_simulations)

    remaining_donalds = remaining_donalds_base + S_undecided * simulated_undecided_alloc[:, 0]
    remaining_collins = remaining_collins_base + S_undecided * simulated_undecided_alloc[:, 1]
    remaining_fishback = remaining_fishback_base + S_undecided * simulated_undecided_alloc[:, 2]
    remaining_other_named = S_other  # Other_Named no recibe indecisos (igual que antes)

    # --- Early vote (su propia Dirichlet, su propia confianza) ---
    early_alpha = [ev_shares[c] * early_confidence for c in ['Donalds', 'Collins', 'Fishback']]
    early_alpha.append(ev_others * early_confidence)
    early_alpha = [max(a, 1e-3) for a in early_alpha]
    simulated_early_shares = rng.dirichlet(early_alpha, size=n_simulations)

    # --- Turnout (su propia incertidumbre) ---
    simulated_turnout = rng.normal(total_expected_turnout, total_expected_turnout * turnout_cv_value, size=n_simulations)
    simulated_turnout = np.clip(simulated_turnout, total_early_votes, None)
    simulated_pct_remaining = 1.0 - (total_early_votes / simulated_turnout)
    simulated_p_early = 1.0 - simulated_pct_remaining

    # --- Nivel 3: Renner vs Other_Residual (dentro de Other_Named). FIX
    # v5: una fracción SIMULADA por draw (Beta(r_alpha, r_beta)) en vez de
    # un punto fijo -- propaga la incertidumbre de estimarlo sobre solo 10
    # encuestas pareadas, y usa la MISMA fracción para partir tanto el
    # tramo early vote como el remaining de cada simulación (es la misma
    # composición interna de "Other_Named", no dos cantidades independientes).
    # FIX v6 (bug #15): r_alpha/r_beta ahora pueden venir override desde
    # recompute_and_simulate() cuando half_life cambia el Poll_Weight con
    # el que se ajustó esta Beta -- antes se reusaba siempre la del
    # modelo base sin importar qué half_life se estuviera probando.
    simulated_renner_split = rng.beta(r_alpha, r_beta, size=n_simulations)

    # --- Combinar early + remaining, y partir Other_Named en Renner / Other_Residual ---
    sim = pd.DataFrame(index=range(n_simulations), columns=['Donalds', 'Collins', 'Fishback', 'Renner', 'Other_Residual'], dtype=float)
    sim['Donalds'] = (simulated_early_shares[:, 0] * simulated_p_early) + (remaining_donalds * simulated_pct_remaining)
    sim['Collins'] = (simulated_early_shares[:, 1] * simulated_p_early) + (remaining_collins * simulated_pct_remaining)
    sim['Fishback'] = (simulated_early_shares[:, 2] * simulated_p_early) + (remaining_fishback * simulated_pct_remaining)
    sim['Renner'] = (simulated_early_shares[:, 3] * simulated_renner_split * simulated_p_early) + \
        (remaining_other_named * simulated_renner_split * simulated_pct_remaining)
    sim['Other_Residual'] = (simulated_early_shares[:, 3] * (1 - simulated_renner_split) * simulated_p_early) + \
        (remaining_other_named * (1 - simulated_renner_split) * simulated_pct_remaining)

    winner_pool = ['Donalds', 'Collins', 'Fishback', 'Renner']  # Other_Residual NO compite
    sim['Winner'] = sim[winner_pool].idxmax(axis=1)

    if verbose:
        print(f"\nkappa nivel 0 (Undecided vs. Decided, Beta moment-matched): {kappa_ud:.1f}")
        print(f"kappa nivel 1 (Other_Named vs. Pool_Candidatos dentro de Decided, Beta moment-matched): {kappa_od:.1f}")
        print(f"kappa nivel 2 (Donalds/Collins/Fishback dentro del pool): {[round(k, 1) for k in within_kappas]} -> usado: {kappa_within:.1f}")
        print(f"kappa nivel 3 (Renner vs. Other_Residual dentro de Other_Named, Beta moment-matched): {renner_split_kappa:.1f}"
              if renner_split_alpha_ov is None else f"kappa nivel 3 (override): a={r_alpha:.2f}, b={r_beta:.2f}")

    return {
        'sim_results': sim,
        'winner_pool': winner_pool,
        'n_simulations': n_simulations,
    }


def recompute_and_simulate(half_life_value=None, use_house_effects=True, prior_overrides=None,
                            undecided_center=None, early_vote_shift=None, other_named_avg_override=None,
                            turnout_cv_override=None, n_simulations=10_000, seed=42):
    """
    FIX v5 (punto #6 de la revisión más reciente): a diferencia de
    EARLY_VOTE_CONFIDENCE/UNDECIDED_ALLOCATION_CONFIDENCE/TURNOUT_CV_ASSUMED
    (parámetros de CONFIANZA/dispersión que solo afectan al Monte Carlo),
    half_life, house_effects y subjective_priors son supuestos
    ESTRUCTURALES que cambian el ponderado de encuestas y el ensemble
    Bayesiano ANTES de llegar al Monte Carlo. Para medir su efecto hay que
    re-correr esa parte del pipeline (celdas 2 y 3), no solo el Monte
    Carlo. Esta función reproduce esas celdas sobre una COPIA de
    polls_rep (nunca toca las variables globales del modelo base) para un
    valor alternativo de half_life / house effects on-off / priors /
    centro de reparto de indecisos, y corre el Monte Carlo resultante.

    FIX v6 (punto #5 de la revisión más reciente): se agrega
    early_vote_shift (dict opcional {'Donalds': delta, 'Collins': delta,
    ...} en PUNTOS FRACCIONALES) para poder construir escenarios
    ADVERSOS explícitos -- p.ej. mover -5pts a Donalds y +5pts a Collins
    en el prior de early vote -- en vez de solo escenarios que favorecen
    a Donalds (limitación señalada explícitamente por el usuario: la
    sensibilidad de priors en v5 solo probaba Donalds +5).

    FIX v7 (punto #1 de la revisión más reciente, el de mayor impacto):
    se agregan other_named_avg_override y turnout_cv_override para poder
    combinar TODOS los supuestos adversos en un solo escenario ("stress
    test pesimista"), en vez de solo probarlos uno a la vez. El usuario
    señaló que los efectos individuales (indecisos adversos -6.7pts,
    early vote adverso -5.4pts, priors adversos -3.2pts) no deben sumarse
    mecánicamente porque el modelo es no lineal -- por eso se corre el
    escenario conjunto explícitamente en vez de solo sumar los deltas.
    """
    hl = half_life_value if half_life_value is not None else half_life
    decay = np.log(2) / hl
    df = polls_rep.copy()

    effects = house_effects if use_house_effects else {}
    for cand in ['Donalds', 'Collins', 'Fishback']:
        df[f'{cand}_Adj'] = df.apply(lambda r: apply_house_effects(r, cand, effects), axis=1)

    df['Poll_Weight'] = df['Sample'] * np.exp(-decay * df['Days_Since_Poll'])

    pol_avg, pol_std = {}, {}
    for cand in ['Donalds', 'Collins', 'Fishback']:
        m = weighted_average(df, f'{cand}_Adj', 'Poll_Weight')
        s = poll_dispersion(df, f'{cand}_Adj', 'Poll_Weight', m)
        pol_avg[cand] = m / 100.0
        pol_std[cand] = s / 100.0

    paired = df.dropna(subset=['Renner', 'Other'])
    if not paired.empty:
        o_avg = weighted_average(paired, 'Other_Named_Total', 'Poll_Weight') / 100.0
        o_std = poll_dispersion(paired, 'Other_Named_Total', 'Poll_Weight', o_avg * 100) / 100.0
    else:
        o_avg, o_std = other_named_avg, other_named_std
    if other_named_avg_override is not None:
        o_avg = other_named_avg_override

    # FIX v6 (bug #15 de la revisión más reciente): el split Renner/Other
    # también depende de Poll_Weight (usa las mismas encuestas pareadas
    # con sus pesos), así que también debe recalcularse con el half_life
    # alternativo -- antes esta función recalculaba TODO excepto esto, y
    # el Monte Carlo terminaba usando la Beta ajustada con el half_life
    # BASE (14 días) sin importar qué half_life se estuviera probando.
    r_frac, r_alpha, r_beta, r_kappa, _ = fit_renner_split_beta(paired)

    u_avg = weighted_average(df, 'Undecided', 'Poll_Weight') / 100.0
    u_std = poll_dispersion(df, 'Undecided', 'Poll_Weight', u_avg * 100) / 100.0

    priors_use = prior_overrides if prior_overrides is not None else subjective_priors
    posteriors = {}
    for cand in priors_use.keys():
        pm, ps = priors_use[cand]['mean'], priors_use[cand]['std']
        dm, ds = pol_avg[cand], pol_std[cand]
        post_m, post_s = bayesian_update(pm, ps, dm, ds)
        posteriors[cand] = {'mean': post_m, 'std': post_s}

    alloc = undecided_center if undecided_center is not None else undecided_allocation
    final_est = {c: posteriors[c]['mean'] + u_avg * alloc[c] for c in posteriors}
    ev_shares = {c: final_est[c] for c in ['Donalds', 'Collins', 'Fishback']}
    if early_vote_shift:
        for cand, delta in early_vote_shift.items():
            ev_shares[cand] = max(ev_shares[cand] + delta, 0.0)
    ev_others = max(1.0 - sum(ev_shares.values()), 0.0)

    turnout_cv_use = turnout_cv_override if turnout_cv_override is not None else TURNOUT_CV_ASSUMED

    return run_monte_carlo(
        EARLY_VOTE_CONFIDENCE, UNDECIDED_ALLOCATION_CONFIDENCE, turnout_cv_use,
        n_simulations=n_simulations, seed=seed,
        ensemble_posteriors_ov=posteriors, other_named_avg_ov=o_avg, other_named_std_ov=o_std,
        undecided_avg_ov=u_avg, undecided_std_ov=u_std, undecided_allocation_ov=alloc,
        early_vote_point_shares_ov=ev_shares, early_vote_others_share_ov=ev_others,
        renner_split_alpha_ov=r_alpha, renner_split_beta_ov=r_beta,
    )


def format_win_prob(n_wins, n_total):
    """
    FIX v6 (puntos #6/#11/#12/#13 de la revisión más reciente): con
    10,000 simulaciones y P(Donalds) saturada cerca de 99.9-100%, el
    tercer/cuarto decimal (99.94 vs 99.96 vs 99.99) es ruido Monte Carlo,
    no señal -- una diferencia de 1 a 6 derrotas sobre 10,000 simulaciones
    "parece" distinta pero no lo es de forma confiable. Esta función
    centraliza el formato "regla de tres" (ya usado en el bloque principal
    de PROBABILIDAD DE VICTORIA) para que las tablas de sensibilidad usen
    la MISMA disciplina en vez de imprimir "100.00%" literal cuando hubo
    0 derrotas -- antes esto contradecía al bloque principal.
    """
    upper_loss_bound = 3.0 / n_total * 100
    if n_wins == n_total:
        return f">{100 - upper_loss_bound:.2f}%"
    elif n_wins == 0:
        return f"<{upper_loss_bound:.2f}%"
    else:
        return f"{n_wins / n_total * 100:.2f}%"


result = run_monte_carlo(EARLY_VOTE_CONFIDENCE, UNDECIDED_ALLOCATION_CONFIDENCE, TURNOUT_CV_ASSUMED, verbose=True)
sim_results = result['sim_results']
candidates_list = result['winner_pool']
winner_candidates_list = candidates_list + ['Other_Residual']
n_simulations = result['n_simulations']
win_probabilities = sim_results['Winner'].value_counts(normalize=True) * 100

print("-" * 40)
print("PROBABILIDAD DE VICTORIA (Tras 10,000 Simulaciones):")
print("NOTA: probabilidades CONDICIONALES a este modelo (priors, asignación de indecisos, supuestos de "
      "early vote/turnout) -- NO son probabilidades electorales calibradas; para eso haría falta "
      "backtesting contra elecciones pasadas.")
for cand in candidates_list:
    n_wins = int((sim_results['Winner'] == cand).sum())
    display_prob = format_win_prob(n_wins, n_simulations)
    extra = ""
    if n_wins == n_simulations:
        extra = " (0 derrotas -> límite superior de pérdida ~3/n al 95% unilateral, regla de tres)"
    print(f" ► {cand}: {display_prob} ({n_wins:,}/{n_simulations:,} simulaciones ganadas){extra}")
print("-" * 40)

print("\nRANGOS PROBABLES DE VOTO (Intervalo del 95%):")
for cand in winner_candidates_list:
    lower_bound = np.percentile(sim_results[cand], 2.5) * 100
    upper_bound = np.percentile(sim_results[cand], 97.5) * 100
    median_vote = np.median(sim_results[cand]) * 100
    tag = "" if cand != 'Other_Residual' else "  (no compite por la victoria)"
    print(f" ► {cand}: Mediana {median_vote:.1f}%  (Rango: {lower_bound:.1f}% - {upper_bound:.1f}%){tag}")

# FIX v5 (punto CRÍTICO #3 de la revisión más reciente): "suma de medianas
# marginales" NO es un chequeo válido de conservación de masa. La mediana
# no es aditiva -- Median(X+Y) != Median(X)+Median(Y) en general -- así
# que sum(mediana_i) puede desviarse de 100% sin que haya NINGÚN error de
# composición, y el número anterior (¬98.9%) no probaba ni refutaba nada.
# El chequeo correcto es fila a fila: cada simulación individual (cada
# draw del Monte Carlo) SÍ debe sumar exactamente 1 entre todas las
# categorías competidoras + Other_Residual, porque así se construyó la
# composición (Dirichlet + partición determinística de Other_Named).
row_sums = sim_results[winner_candidates_list].sum(axis=1)
max_abs_dev = np.max(np.abs(row_sums - 1.0))
print(f"\n[Chequeo de consistencia] Suma fila a fila (por simulación) de todas las categorías: "
      f"min={row_sums.min()*100:.4f}%, max={row_sums.max()*100:.4f}%, "
      f"desviación máxima absoluta respecto a 100%: {max_abs_dev*100:.6f} pts.")
assert max_abs_dev < 1e-6, "Las simulaciones individuales no suman 1 -- hay una fuga o duplicación en la composición."


# =====================================================================
# CELDA "5. Salidas, Dashboards y Alertas" -- CORREGIDA v3
# =====================================================================
import matplotlib
matplotlib.use('Agg')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

print("\nGenerando Salidas y Visualizaciones...")

sns.set_theme(style="whitegrid")
colors = {'Donalds': 'royalblue', 'Collins': 'goldenrod', 'Fishback': 'mediumseagreen',
          'Renner': 'mediumpurple', 'Other_Residual': 'lightgray'}

plt.figure(figsize=(12, 6))
for cand in winner_candidates_list:
    win_prob = (sim_results['Winner'] == cand).mean() * 100 if cand in candidates_list else 0.0
    label = f"{cand} (Win Prob: {win_prob:.1f}%)" if cand != 'Other_Residual' else f"{cand} (no compite)"
    sns.kdeplot(
        sim_results[cand].astype(float) * 100,
        label=label,
        fill=True,
        alpha=0.4,
        color=colors.get(cand, 'slategray'),
        linewidth=2
    )
# FIX v7 (punto menor #1 de la revisión más reciente): esta primaria se
# gana por PLURALIDAD (el candidato con más votos, sin importar si llega
# a 50%), no por mayoría absoluta -- una línea en 50% etiquetada "Mayoría
# Absoluta" puede sugerirle al lector que ese es el umbral para ganar,
# cuando Donalds puede ganar (y de hecho gana en la mayoría de las
# simulaciones) con un share bien por debajo de 50%. Se deja la línea
# como referencia visual neutra, sin implicar que sea el umbral de victoria.
plt.axvline(x=50, color='gray', linestyle='--', label='50% (referencia visual, NO es el umbral de victoria -- se gana por pluralidad)')
plt.title('Distribución Probable del Voto - Primaria Republicana (Florida 2026)', fontsize=14, fontweight='bold')
plt.xlabel('Porcentaje de Votos Proyectado (%)', fontsize=12)
plt.ylabel('Densidad de Simulaciones', fontsize=12)
plt.legend(loc='upper right', frameon=True)
plt.tight_layout()
plt.savefig('election_forecast_density.png', dpi=300)


# FIX v3 (punto #21): se agrega Renner y Otros a la tabla de
# sensibilidad -- antes Donalds+Collins+Fishback no sumaban 100% porque
# el resto del electorado simplemente se omitía de la tabla.
# FIX v4 (punto CRÍTICO #7 de la revisión): la v3 sumaba 101-102% aquí
# porque usaba renner_avg + other_avg calculados sobre encuestas
# DISTINTAS (33 vs. 11). Ahora se parte SIEMPRE other_named_avg (una
# sola cantidad consistente) con renner_split_frac (estimado solo sobre
# las encuestas que reportan ambas columnas) -- igual que en Monte Carlo.
print("\n--- ANÁLISIS DE SENSIBILIDAD (TURNOUT) ---")
turnout_scenarios = [1.2e6, 1.4e6, 1.5e6, 1.6e6, 1.8e6]
sensitivity_results = []
sens_candidates = ['Donalds', 'Collins', 'Fishback', 'Renner', 'Other_Residual']
sens_point = {
    'Donalds': ensemble_estimates['Donalds']['mean'],
    'Collins': ensemble_estimates['Collins']['mean'],
    'Fishback': ensemble_estimates['Fishback']['mean'],
    'Renner': other_named_avg * renner_split_frac,
    'Other_Residual': other_named_avg * (1 - renner_split_frac),
}

# FIX v5 (punto CRÍTICO #2 de la revisión más reciente): sens_point NO
# sumaba exactamente 1 antes de combinarse con early_point_full. La causa
# es la misma "closure_gap" ya diagnosticada arriba: final_ensemble_estimates
# reparte el 100% del undecided_pool sobre D/C/F, pero
# D+C+F(posterior) + undecided_pool + other_named_avg no tiene por qué
# sumar exactamente 1 (el update Bayesiano es de 3 Normales independientes,
# sin la restricción de composición -- ver nota en bayesian_update). El
# desajuste es justamente closure_gap = {closure_gap*100:+.2f} pts, y es lo
# que hacía que la tabla de sensibilidad no cerrara a 100.0%. Se
# renormaliza aquí explícitamente para que el punto central usado en la
# tabla sea una composición válida (suma exacta 1), documentando la
# magnitud del ajuste en vez de dejarlo como un error silencioso de ~0.1-1.6pt.
_sens_total_raw = sum(sens_point.values())
print(f"\n[Normalización sens_point] Suma cruda antes de renormalizar: {_sens_total_raw*100:.2f}% "
      f"(gap = {(_sens_total_raw - 1.0)*100:+.2f} pts, mismo origen que closure_gap). "
      f"Se renormaliza dividiendo cada categoría por la suma cruda.")
sens_point = {k: v / _sens_total_raw for k, v in sens_point.items()}

early_point_full = dict(early_vote_point_shares)
early_point_full['Renner'] = early_vote_others_share * renner_split_frac
early_point_full['Other_Residual'] = early_vote_others_share * (1 - renner_split_frac)

for t in turnout_scenarios:
    p_early_scn = total_early_votes / t
    p_rem_scn = 1.0 - p_early_scn
    c_shares = []
    for cand in sens_candidates:
        val = (early_point_full[cand] * p_early_scn) + (sens_point[cand] * p_rem_scn)
        c_shares.append(val)
    row_total = sum(c_shares)
    sensitivity_results.append([f"{t/1e6:.1f}M"] + [f"{v*100:.1f}%" for v in c_shares] + [f"{row_total*100:.1f}%"])

sens_df = pd.DataFrame(sensitivity_results, columns=['Turnout Total (Millones)'] + sens_candidates + ['Suma'])
print(sens_df.to_string(index=False))

# FIX v3 (punto #22): se separan alertas ELECTORALES (¿está cerrada la
# carrera bajo este modelo?) de alertas de CALIDAD METODOLÓGICA (¿qué
# supuestos sin validar sostienen ese resultado?). Mezclarlas hacía que
# "sin alertas" se leyera como "sin riesgo", cuando en realidad solo
# significaba "no detecto una carrera cerrada dado lo que asumí".
print("\n--- ALERTAS ELECTORALES (bajo los supuestos de este modelo) ---")
alert_triggered = False

donalds_margin = sim_results['Donalds'].mean() - sim_results['Collins'].mean()
if donalds_margin < 0.05:
    print("⚠️ ALERTA: La ventaja de Donalds ha caído a menos de 5 puntos. Revisar modelo de indecisos.")
    alert_triggered = True

win_prob_leader = win_probabilities.max()
if win_prob_leader < 90:
    print(f"⚠️ ALERTA: La probabilidad de victoria del líder ({win_prob_leader:.1f}%) bajó de 90%. Carrera competitiva.")
    alert_triggered = True

if not alert_triggered:
    print("✅ Bajo los supuestos actuales del modelo, no se detecta una carrera cerrada.")

print("\n--- ALERTAS DE CALIDAD METODOLÓGICA (siempre vigentes, no dependen del resultado) ---")
methodology_warnings = []
if polls_rep['Sample_Imputed'].mean() > 0.5:
    methodology_warnings.append(
        f"100% de tamaños de muestra (Sample) son imputados -- el ponderador no discrimina por calidad de muestra."
    )
methodology_warnings.append(
    "House effects (Targoz, Change Research, RealClearPolitics) son ajustes manuales por encuestadora, "
    "no parámetros calibrados históricamente."
)
methodology_warnings.append(
    "Los priors 'subjective_priors' (fundamentales) son supuestos subjetivos, no estimados desde 2018/2022, "
    "demografía, fundraising o endorsements."
)
methodology_warnings.append(
    "La preferencia de candidato en el voto anticipado no se observa -- se centra en el ensemble general "
    "con confianza declarada baja (EARLY_VOTE_CONFIDENCE)."
)
methodology_warnings.append(
    "El reparto de indecisos (60/25/15) es un supuesto simulado con confianza declarada baja "
    "(UNDECIDED_ALLOCATION_CONFIDENCE), no una medición."
)
methodology_warnings.append(
    "El turnout esperado de 2026 se basa esencialmente en un solo precedente histórico válido (2018); "
    "2022 se excluyó por no tener primaria REP competitiva (ver auditoría celda 1)."
)
methodology_warnings.append(
    "El CV de turnout (12%) es un hiperparámetro asumido -- NO tiene una fuente ni calibración citable "
    "dentro de este notebook, y no debe presentarse como 'literatura' sin verificar esa cita."
)
methodology_warnings.append(
    "Reg_2018/Pct_2018 (turnout_hist) son tasas de TODOS los partidos, no específicas de republicanos "
    "(verificado: Reg_2018 correlaciona 0.996 con el padrón total 2026, y es ~2x el padrón solo-REP 2026). "
    "El turnout esperado asume que los republicanos participan a la misma tasa que el electorado general "
    "-- un supuesto no verificado, no un hecho medido."
)
methodology_warnings.append(
    "EARLY_VOTE_CONFIDENCE, UNDECIDED_ALLOCATION_CONFIDENCE y TURNOUT_CV_ASSUMED son hiperparámetros "
    "elegidos a mano -- ver la celda de sensibilidad para cuánto mueven P(win) por sí solos."
)
methodology_warnings.append(
    "El forecast no tiene backtesting contra elecciones pasadas -- P(win) es condicional al modelo, "
    "no una probabilidad electoral calibrada."
)
# FIX v7 (puntos #5/#6 de la revisión más reciente -- limitaciones NO
# resueltas en v7 porque no se pueden arreglar con ingeniería, solo con
# datos que hoy no existen en esta carpeta; se documentan explícitamente
# en vez de dejarlas implícitas):
methodology_warnings.append(
    "Turnout y preferencia de candidato están DESACOPLADOS en este modelo: TURNOUT_CV mueve principalmente "
    "el balance Early/Remaining, pero no hay ninguna relación modelada entre composición demográfica/"
    "geográfica del turnout y preferencia (p.ej. más turnout en un condado o grupo de edad no cambia la "
    "composición de apoyo) -- por eso la sensibilidad a TURNOUT_CV en el margen es casi plana por "
    "construcción, no porque el turnout real sea irrelevante para el resultado."
)
methodology_warnings.append(
    "poll_dispersion() mide dispersión ENTRE encuestas, no un error estándar calibrado del agregado -- "
    "esa dispersión alimenta el likelihood Bayesiano, las kappas y las Betas del árbol composicional, así "
    "que parte de la incertidumbre final del Monte Carlo viene de un proxy (between-poll dispersion), no de "
    "un modelo de encuestas calibrado (requeriría un modelo jerárquico con house effects, time effects y "
    "sampling error explícitos)."
)
for w in methodology_warnings:
    print(f"⚠ {w}")


# =====================================================================
# CELDA "6. Sensibilidad de Hiperparámetros" -- NUEVA v4
# =====================================================================
import numpy as np
import pandas as pd

# FIX v4 (punto crítico #19 de la revisión): EARLY_VOTE_CONFIDENCE,
# UNDECIDED_ALLOCATION_CONFIDENCE y TURNOUT_CV_ASSUMED son supuestos,
# no mediciones. Antes de seguir refinando el número central del
# forecast, vale más saber cuánto lo mueve cada uno de estos tres
# hiperparámetros por sí solo (análisis "tornado": se varía uno a la
# vez, dejando los otros dos en su valor base).
print("Corriendo análisis de sensibilidad de hiperparámetros (esto toma unos segundos)...\n")

BASE_EARLY_CONF = EARLY_VOTE_CONFIDENCE
BASE_UNDECIDED_CONF = UNDECIDED_ALLOCATION_CONFIDENCE
BASE_TURNOUT_CV = TURNOUT_CV_ASSUMED

scenario_grids = {
    'EARLY_VOTE_CONFIDENCE': [10, 25, 50, 100],
    'UNDECIDED_ALLOCATION_CONFIDENCE': [5, 10, 20, 50],
    'TURNOUT_CV_ASSUMED': [0.05, 0.10, 0.15, 0.20],
}

tornado_rows = []
for param_name, grid in scenario_grids.items():
    for value in grid:
        kwargs = dict(early_confidence=BASE_EARLY_CONF,
                       undecided_confidence=BASE_UNDECIDED_CONF,
                       turnout_cv_value=BASE_TURNOUT_CV)
        if param_name == 'EARLY_VOTE_CONFIDENCE':
            kwargs['early_confidence'] = value
        elif param_name == 'UNDECIDED_ALLOCATION_CONFIDENCE':
            kwargs['undecided_confidence'] = value
        else:
            kwargs['turnout_cv_value'] = value

        r = run_monte_carlo(**kwargs, n_simulations=10_000, seed=42)
        sim = r['sim_results']
        n_tot = r['n_simulations']
        n_donalds = int((sim['Winner'] == 'Donalds').sum())
        n_collins = int((sim['Winner'] == 'Collins').sum())
        median_margin = (np.median(sim['Donalds']) - np.median(sim['Collins'])) * 100
        lo = np.percentile(sim['Donalds'], 2.5) * 100
        hi = np.percentile(sim['Donalds'], 97.5) * 100
        is_base = (
            (param_name == 'EARLY_VOTE_CONFIDENCE' and value == BASE_EARLY_CONF) or
            (param_name == 'UNDECIDED_ALLOCATION_CONFIDENCE' and value == BASE_UNDECIDED_CONF) or
            (param_name == 'TURNOUT_CV_ASSUMED' and value == BASE_TURNOUT_CV)
        )
        tornado_rows.append({
            'Hiperparámetro': param_name,
            'Valor': value,
            '(base)': 'sí' if is_base else '',
            # FIX v6 (puntos #6/#11/#12/#13): formato regla-de-tres, MISMA
            # disciplina que el bloque principal -- ya no imprime "100.00%"
            # literal cuando hubo 0 derrotas sobre 10,000.
            'P(Donalds gana)': format_win_prob(n_donalds, n_tot),
            'P(Collins gana)': format_win_prob(n_collins, n_tot),
            'Margen mediano D-C (pts)': round(median_margin, 1),
            'Donalds IC95%': f"{lo:.1f}%-{hi:.1f}%",
            '_margin_raw': median_margin,  # solo para ranking interno, no se imprime
        })

tornado_df = pd.DataFrame(tornado_rows)
print(tornado_df.drop(columns=['_margin_raw']).to_string(index=False))

# FIX v6 (punto #12 de la revisión más reciente): con P(Donalds) saturada
# cerca de 99.9-100%, comparar 99.94 vs 99.96 vs 99.99 es comparar ruido
# Monte Carlo (1 a 6 derrotas sobre 10,000), no señal real. El margen
# mediano D-C es la métrica que SÍ es informativa en esta zona -- el
# ranking de "qué hiperparámetro importa más" se hace sobre el margen,
# no sobre P(win).
print("\n--- LECTURA ---")
print("NOTA: P(Donalds gana) está saturada (>99.9% en casi todos los escenarios) -- comparar sus "
      "decimales entre escenarios es comparar ruido Monte Carlo (diferencias de 1-6 derrotas sobre "
      "10,000), no señal. La métrica informativa aquí es el margen mediano D-C.")
for param_name in scenario_grids:
    sub = tornado_df[tornado_df['Hiperparámetro'] == param_name]
    spread = sub['_margin_raw'].max() - sub['_margin_raw'].min()
    print(f"{param_name}: margen mediano D-C varía {spread:.1f} pts entre los escenarios probados "
          f"({sub['_margin_raw'].min():.1f} - {sub['_margin_raw'].max():.1f} pts).")

max_spread_param = max(scenario_grids, key=lambda p: (
    tornado_df[tornado_df['Hiperparámetro'] == p]['_margin_raw'].max()
    - tornado_df[tornado_df['Hiperparámetro'] == p]['_margin_raw'].min()
))
print(f"\nEl hiperparámetro que más mueve el margen mediano D-C es: {max_spread_param}. "
      f"Si el margen real de la carrera se cierra, ESE es el primer supuesto que valdría la pena "
      f"revisar o calibrar con más cuidado -- no el número central del forecast.")

# FIX v5 (punto #6 de la revisión más reciente): la tabla anterior solo
# mueve los parámetros de CONFIANZA (dispersión) del Monte Carlo. Faltan
# los supuestos ESTRUCTURALES que definen el CENTRO del modelo:
#   - el centro del reparto de indecisos (60/25/15, hoy fijo)
#   - half_life=14 días (especialmente relevante porque Sample está
#     100% imputado -- Poll_Weight hoy depende ÚNICAMENTE del decaimiento
#     temporal, así que half_life es, de facto, el único mando que
#     controla cuánto peso relativo tienen las encuestas recientes)
#   - los house effects (activados/desactivados)
#   - los subjective_priors (fundamentales) en sí, no solo su std
# Cada escenario recalcula ponderación + ensemble desde cero vía
# recompute_and_simulate() -- son corridas más lentas que la tabla
# anterior, por eso se usan menos puntos por parámetro.
print("\n\nCorriendo sensibilidad ESTRUCTURAL (half_life, house effects, priors, centro de indecisos, "
      "missingness de Other_Named, escenarios adversos)...\n")

# FIX v6 (punto #14 de la revisión más reciente): en v5 la sensibilidad de
# priors y de indecisos SOLO probaba escenarios que favorecían a Donalds
# (Donalds +5pts; indecisos 50/30/20 pero Donalds seguía recibiendo 50%,
# por ENCIMA de su ~45% de polling inicial). Eso no contesta la pregunta
# relevante: "¿qué tan dependiente es mi conclusión de mi prior
# subjetivo?" -- para eso hace falta el escenario espejo, genuinamente
# ADVERSO a Donalds, no solo "menos favorable".
shifted_priors_favorable = {
    cand: {'mean': subjective_priors[cand]['mean'] + 0.05, 'std': subjective_priors[cand]['std']}
    if cand == 'Donalds' else
    {'mean': max(subjective_priors[cand]['mean'] - 0.025, 0.001), 'std': subjective_priors[cand]['std']}
    for cand in subjective_priors
}
shifted_priors_adverse = {
    cand: {'mean': max(subjective_priors[cand]['mean'] - 0.05, 0.001), 'std': subjective_priors[cand]['std']}
    if cand == 'Donalds' else
    {'mean': subjective_priors[cand]['mean'] + 0.025, 'std': subjective_priors[cand]['std']}
    for cand in subjective_priors
}

structural_scenarios = [
    {'grupo': 'half_life', 'label': '7d (más peso a lo reciente)', 'kwargs': dict(half_life_value=7)},
    {'grupo': 'half_life', 'label': '14d (BASE)', 'kwargs': dict(half_life_value=14), 'is_base': True},
    {'grupo': 'half_life', 'label': '21d', 'kwargs': dict(half_life_value=21)},
    {'grupo': 'half_life', 'label': '30d (casi sin decaimiento)', 'kwargs': dict(half_life_value=30)},
    {'grupo': 'house_effects', 'label': 'Activos (BASE)', 'kwargs': dict(use_house_effects=True), 'is_base': True},
    {'grupo': 'house_effects', 'label': 'Desactivados', 'kwargs': dict(use_house_effects=False)},
    {'grupo': 'indecisos', 'label': '60/25/15 (BASE)', 'kwargs': dict(undecided_center=undecided_allocation), 'is_base': True},
    {'grupo': 'indecisos', 'label': '70/20/10 (favorable a Donalds)',
     'kwargs': dict(undecided_center={'Donalds': 0.70, 'Collins': 0.20, 'Fishback': 0.10})},
    {'grupo': 'indecisos', 'label': '50/30/20 (desfavorable, pero Donalds sigue >su polling)',
     'kwargs': dict(undecided_center={'Donalds': 0.50, 'Collins': 0.30, 'Fishback': 0.20})},
    {'grupo': 'indecisos', 'label': '40/35/25 (ADVERSO: Donalds bajo su polling inicial ~45%)',
     'kwargs': dict(undecided_center={'Donalds': 0.40, 'Collins': 0.35, 'Fishback': 0.25})},
    {'grupo': 'priors', 'label': 'Subjetivos (BASE)', 'kwargs': dict(prior_overrides=subjective_priors), 'is_base': True},
    {'grupo': 'priors', 'label': 'Favorable a Donalds (+5pts, resto -2.5c/u)',
     'kwargs': dict(prior_overrides=shifted_priors_favorable)},
    {'grupo': 'priors', 'label': 'ADVERSO a Donalds (-5pts, resto +2.5c/u)',
     'kwargs': dict(prior_overrides=shifted_priors_adverse)},
    {'grupo': 'early_vote', 'label': 'Centrado en ensemble (BASE)', 'kwargs': dict(), 'is_base': True},
    {'grupo': 'early_vote', 'label': 'ADVERSO (Donalds -5pts, Collins +5pts en el prior de early vote)',
     'kwargs': dict(early_vote_shift={'Donalds': -0.05, 'Collins': 0.05})},
]

structural_rows = []
for scn in structural_scenarios:
    r = recompute_and_simulate(**scn['kwargs'], n_simulations=10_000, seed=42)
    sim = r['sim_results']
    n_tot = r['n_simulations']
    n_donalds = int((sim['Winner'] == 'Donalds').sum())
    n_collins = int((sim['Winner'] == 'Collins').sum())
    median_margin = (np.median(sim['Donalds']) - np.median(sim['Collins'])) * 100
    lo = np.percentile(sim['Donalds'], 2.5) * 100
    hi = np.percentile(sim['Donalds'], 97.5) * 100
    structural_rows.append({
        'Grupo': scn['grupo'],
        'Escenario': scn['label'],
        '(base)': 'sí' if scn.get('is_base') else '',
        'P(Donalds gana)': format_win_prob(n_donalds, n_tot),
        'P(Collins gana)': format_win_prob(n_collins, n_tot),
        'Margen mediano D-C (pts)': round(median_margin, 1),
        'Donalds IC95%': f"{lo:.1f}%-{hi:.1f}%",
    })

# FIX v6 (punto #2 de la revisión más reciente): sensibilidad explícita
# al MISSINGNESS de Other_Named. El salto 7.25% -> 9.21% al pasar de
# min_count=1 (39 encuestas) a solo-pareadas (10 encuestas) fue grande
# (~27% relativo) -- en vez de tratar 9.21% como el valor "correcto" y
# ya, se prueba el rango completo [valor viejo, valor nuevo, un extremo
# más alto] para ver cuánto mueve la conclusión. Se usa other_named_std
# (global, el de la estimación pareada) como dispersión en todos los
# puntos -- esto NO es una sensibilidad de política de missing-data
# completa (para eso se necesitaría, p.ej., inverse-probability weighting
# o un modelo de por qué un poll reporta o no Other), pero acota el rango
# plausible.
other_named_scenarios = [
    ('7.25% (v4, min_count=1 sobre 39 encuestas -- YA IDENTIFICADO COMO SESGADO)', 0.0725, False),
    ('8.20% (punto medio)', 0.0820, False),
    ('9.21% (v5/v6, BASE -- solo 10 encuestas pareadas)', other_named_avg, True),
    ('10.00% (extremo alto, ilustrativo)', 0.1000, False),
]
for label, o_val, is_base in other_named_scenarios:
    r = run_monte_carlo(EARLY_VOTE_CONFIDENCE, UNDECIDED_ALLOCATION_CONFIDENCE, TURNOUT_CV_ASSUMED,
                         n_simulations=10_000, seed=42, other_named_avg_ov=o_val)
    sim = r['sim_results']
    n_tot = r['n_simulations']
    n_donalds = int((sim['Winner'] == 'Donalds').sum())
    n_collins = int((sim['Winner'] == 'Collins').sum())
    median_margin = (np.median(sim['Donalds']) - np.median(sim['Collins'])) * 100
    lo = np.percentile(sim['Donalds'], 2.5) * 100
    hi = np.percentile(sim['Donalds'], 97.5) * 100
    structural_rows.append({
        'Grupo': 'other_named_missingness',
        'Escenario': label,
        '(base)': 'sí' if is_base else '',
        'P(Donalds gana)': format_win_prob(n_donalds, n_tot),
        'P(Collins gana)': format_win_prob(n_collins, n_tot),
        'Margen mediano D-C (pts)': round(median_margin, 1),
        'Donalds IC95%': f"{lo:.1f}%-{hi:.1f}%",
    })

structural_df = pd.DataFrame(structural_rows)
print(structural_df.to_string(index=False))

print("\n--- LECTURA (sensibilidad estructural) ---")
print("half_life: entre más corto, más peso a las encuestas recientes (con Sample 100% imputado, "
      "half_life es hoy el ÚNICO mando real detrás de Poll_Weight -- ver aviso en celda 1).")
print("House effects: activarlos/desactivarlos mueve el punto central según cuánto pesen hoy las "
      "encuestas de Targoz/Change Research/RCP en el promedio ponderado vigente.")
print("Centro de indecisos: 60/25/15 es un supuesto, no una medición -- el escenario 40/35/25 es el "
      "primero genuinamente ADVERSO (deja a Donalds por debajo de su polling inicial ~45%).")
print("Priors subjetivos: se prueban AMBAS direcciones (favorable y adversa a Donalds) para no sesgar "
      "la sensibilidad hacia un solo lado.")
print("Early vote: el escenario adverso mueve 5pts de Donalds a Collins en el prior de early vote "
      "(dato no observado directamente, solo centrado en el ensemble general).")
print("Other_Named (missingness): compara el valor descartado en v4 (7.25%, sesgado por min_count=1) "
      "contra el valor v5/v6 (9.21%, solo encuestas pareadas) y un extremo ilustrativo (10.0%).")
print("\nNOTA: a diferencia de la tabla de EARLY_VOTE_CONFIDENCE/UNDECIDED_ALLOCATION_CONFIDENCE/"
      "TURNOUT_CV_ASSUMED (parámetros de confianza), estos SÍ cambian el número central reportado como "
      "forecast -- por eso es más importante documentarlos explícitamente que 'afinarlos' sin una base "
      "empírica que los respalde. Igual que en la tabla anterior: P(Donalds gana) está saturada -- "
      "el margen mediano D-C es la columna que hay que leer para calibrar impacto real.")

# FIX v7 (punto #1 de la revisión más reciente -- el de MAYOR impacto,
# "el verdadero stress test pesimista para Donalds"): hasta ahora cada
# supuesto adverso se probó UNO A LA VEZ. El usuario señaló que sus
# efectos individuales sobre el margen mediano D-C son aproximadamente:
#   Indecisos adversos (40/35/25):        -6.7 pts
#   Early vote adverso (D-5/C+5):         -5.4 pts
#   Priors adversos (D-5, resto +2.5c/u): -3.2 pts
# y que NO deben sumarse mecánicamente (el modelo es no lineal: los
# splits Dirichlet/Beta normalizan, así que un supuesto adverso interactúa
# con los demás en vez de sumarse linealmente) -- por eso se corre el
# escenario COMBINADO explícitamente, con TODOS los supuestos adversos
# activos simultáneamente (incluyendo también el extremo alto de
# Other_Named y el CV de turnout más alto probado, aunque su efecto
# individual sea pequeño, para que el stress test sea genuinamente el
# peor caso razonable dentro de la gama de escenarios ya probados).
print("\n\n" + "=" * 70)
print("STRESS TEST PESIMISTA -- TODOS LOS SUPUESTOS ADVERSOS COMBINADOS")
print("=" * 70)
print("Combina simultáneamente: priors adversos (Donalds -5pts) + indecisos 40/35/25 "
      "+ early vote adverso (Donalds -5pts/Collins +5pts) + Other_Named=10% (extremo alto) "
      "+ TURNOUT_CV=0.20 (mayor incertidumbre de turnout probada). Esto NO es la suma mecánica "
      "de los deltas individuales -- es la corrida conjunta real del modelo bajo ese escenario.\n")

r_stress = recompute_and_simulate(
    prior_overrides=shifted_priors_adverse,
    undecided_center={'Donalds': 0.40, 'Collins': 0.35, 'Fishback': 0.25},
    early_vote_shift={'Donalds': -0.05, 'Collins': 0.05},
    other_named_avg_override=0.10,
    turnout_cv_override=0.20,
    n_simulations=10_000, seed=42,
)
sim_stress = r_stress['sim_results']
n_tot_stress = r_stress['n_simulations']
n_donalds_stress = int((sim_stress['Winner'] == 'Donalds').sum())
n_collins_stress = int((sim_stress['Winner'] == 'Collins').sum())
median_margin_stress = (np.median(sim_stress['Donalds']) - np.median(sim_stress['Collins'])) * 100
lo_stress = np.percentile(sim_stress['Donalds'], 2.5) * 100
hi_stress = np.percentile(sim_stress['Donalds'], 97.5) * 100

print(f"P(Donalds gana):        {format_win_prob(n_donalds_stress, n_tot_stress)} "
      f"({n_donalds_stress:,}/{n_tot_stress:,})")
print(f"P(Collins gana):        {format_win_prob(n_collins_stress, n_tot_stress)} "
      f"({n_collins_stress:,}/{n_tot_stress:,})")
print(f"Margen mediano D-C:     {median_margin_stress:.1f} pts (BASE: 38.5 pts)")
print(f"Donalds IC95%:          {lo_stress:.1f}%-{hi_stress:.1f}%")
print(f"\nLECTURA: incluso combinando TODOS los supuestos adversos probados a la vez, el margen mediano "
      f"queda en {median_margin_stress:.1f} pts -- {'todavía claramente positivo para Donalds' if median_margin_stress > 5 else 'la carrera se acerca sustancialmente bajo este escenario conjunto'}. "
      f"Esto es lo que respalda con más fuerza la conclusión cualitativa 'Donalds es favorito muy fuerte': "
      f"no solo bajo el escenario central, sino incluso bajo el peor caso razonable dentro de la gama de "
      f"supuestos individuales ya explorada. Sigue sin ser una probabilidad electoral calibrada -- ver "
      f"limitaciones de turnout GOP y de encuestas no calibradas documentadas arriba.")
print("=" * 70)
