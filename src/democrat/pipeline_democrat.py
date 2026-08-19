import pandas as pd
import numpy as np
import re

# =====================================================================
# CELDA "1. Ingesta y Limpieza (Demócrata)" -- NUEVA v1 (basada en v7 Rep)
# =====================================================================
print("Cargando archivos de datos (primaria DEMÓCRATA)...")

polls_dem = pd.read_excel('Florida_Polls_Clean_2026Primary.xlsx', sheet_name='Dem_Primary_Polls')

# FIX v8: se renombra la columna cruda 'Other' -> 'Other_Minor' desde la
# ingesta. Hasta v7 esa columna era una bolsa genérica "todo lo que no es
# Jolly/Foster"; a partir de v8, Dotie Joseph se separa como candidata
# individual (ver DECISIÓN METODOLÓGICA v8 más abajo), así que lo que
# queda aquí es específicamente Castillo-Bach + Fernandez + Norman
# (agregados) más cualquier indeciso que el pollster haya agrupado ahí --
# 'Other_Minor' es un nombre más preciso para lo que la columna representa
# ahora que 'Other'.
polls_dem = polls_dem.rename(columns={'Other': 'Other_Minor'})

ev_summary = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Summary_by_County')
ev_demographics = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Full_Data')
ev_statewide = pd.read_excel('Florida_EarlyVoting_Joined_2026Primary.xlsx', sheet_name='Statewide_Totals')
turnout_hist = pd.read_excel('Florida_Governor_Primary_Turnout_2018_2022.xlsx', sheet_name='Turnout_by_County')

print("Limpiando base de encuestas DEM...")

TODAY = pd.Timestamp('2026-08-17')

# NOTA IMPORTANTE (adaptación del modelo republicano v7): la hoja
# Dem_Primary_Polls tiene una estructura MATERIALMENTE distinta a
# Rep_Primary_Polls, no solo "los mismos nombres de columna con otros
# candidatos":
#   - Solo 10 filas (vs. 39 del lado republicano) antes de deduplicar.
#   - NO existe una columna 'Undecided' reportada -- ninguna encuesta
#     Demócrata trae indecisos como columna propia.
#   - 'Demings' aparece en 7/10 encuestas pero NO existe como categoría
#     separada en la hoja de referencia Dem_Average.
#   - 'Sample' está PARCIALMENTE poblado (6/10), no 100% vacío como en
#     el lado republicano.
#
# =====================================================================
# CORRECCIÓN CRÍTICA v5 -- RETIRO DE JERRY DEMINGS DE LA CONTIENDA
# =====================================================================
# En v1-v4 este pipeline modeló a Jerry Demings como tercer candidato
# propio del pool principal (Jolly/Foster/Demings), a partir de que 7/10
# filas crudas la reportaban. La auditoría v4 del usuario señaló, como
# hallazgo CRÍTICO y prioritario sobre cualquier ajuste estadístico, que
# ese supuesto ya no es válido: Demings suspendió su candidatura a
# gobernadora antes de la fecha de corte de este modelo.
#
# Verificación (búsqueda web, requerida por política ante cualquier
# afirmación política/electoral vigente -- no se asume por confianza en
# lo que reporta el usuario, se confirma con fuentes primarias):
#   - Jerry Demings suspendió su campaña el 5 de junio de 2026, tras un
#     diagnóstico de cáncer tratable (fuente: Florida Phoenix; también
#     reportado por Tampa Bay Times y WFLA).
#   - CORRECCIÓN v6 (fecha señalada como incorrecta en la auditoría v5):
#     Dotie Joseph presentó su papelería ("filed") el 11-jun-2026 y quedó
#     oficialmente CALIFICADA ("qualified") el 12-jun-2026 -- un día antes
#     del cierre del período de calificación de Florida (viernes
#     12-jun-2026 a las 3pm), según cobertura de Florida Politics/Miami
#     Times y spokesman.com sobre el cierre del período de calificación.
#     v5 afirmaba que se había sumado el 5-jul-2026 -- esa fecha
#     corresponde a la cobertura mediática de su candidatura (Local10,
#     5-jul-2026; CBS Miami, 12-jul-2026) sobre su lanzamiento público,
#     NO a su fecha de calificación oficial, que es casi un mes anterior.
#     Esto importa: significa que Joseph YA estaba calificada cuando se
#     realizaron las DOS encuestas dominantes (Change Research 9-11 jul,
#     Targoz 20-26 jul) -- a diferencia de lo que decía v5 (que ninguna
#     encuesta pudo haberla incluido porque aún no existía como
#     candidata). No se pudo confirmar de forma directa la página de la
#     Florida Division of Elections (dos.elections.myflorida.com no
#     respondió en la verificación), así que esta fecha se reporta con
#     confianza media-alta, no absoluta.
#   - El roster demócrata oficialmente calificado para gobernador, según
#     la Florida Division of Elections (vía Ballotpedia/Florida
#     Phoenix/Local10), es: David Jolly, Dotie Joseph, Dayna Marie
#     Foster, Evelyn Castillo-Bach, Thomas Eloy Fernandez y Stephann
#     Norman. Demings NO forma parte de ese roster (status: Withdrew).
#
# Confirmación adicional con DATOS PROPIOS de este notebook (no solo con
# la fuente externa): si el retiro de Demings es real y tiene fecha
# efectiva 5-jun-2026, el patrón de missingness de la columna 'Demings'
# en las 7 encuestas (tras deduplicar) debería alinearse con esa fecha
# -- encuestas ANTERIORES al retiro deberían reportarla, encuestas
# POSTERIORES no. Se verifica explícitamente más abajo con un crosstab
# fecha-vs-missingness (no se da por sentado el relato, se comprueba).
#
# DECISIÓN METODOLÓGICA (resuelta con el usuario vía pregunta directa,
# porque es una decisión que cambia resultados y no tiene una respuesta
# "correcta" única): con Demings fuera de winner_pool, ¿qué hacer con
# las 5 encuestas pre-retiro (dic-2025 a mar-2026) que sí la incluían?
# Se presentaron dos opciones -- (1) conservar las 7 encuestas para todo
# lo demás (Jolly/Foster/Other) pero excluir la columna Demings del
# cómputo por completo; o (2) recortar el dataset a solo las 2 encuestas
# posteriores al retiro. El usuario eligió explícitamente la OPCIÓN 1
# (recomendada): mantener las 7 encuestas, quitar a Demings del cómputo.
#
# NOTA v6 (la auditoría v5 encontró que la primera implementación de la
# Opción 1, en v5, tenía un defecto): en v5, "excluir a Demings del
# cómputo" se interpretó de forma demasiado literal -- su valor histórico
# simplemente no se restaba de 100%, así que terminaba DENTRO de
# Unallocated_Residual sin querer (contado como indeciso genérico). Eso
# NO es lo mismo que "excluirla del cómputo": un valor MEDIDO que cae por
# descuido en el residuo sigue distorsionando el residuo. FIX v6:
# Retired_Mass (su valor histórico) ahora se resta EXPLÍCITAMENTE al
# calcular Unallocated_Residual (ver más abajo) -- de modo que ni entra a
# ningún promedio ponderado NI infla el residuo. Se implementa así:
#   - DEM_CANDIDATE_COLS (abajo) sigue incluyendo 'Demings' -- se
#     necesita para deduplicar correctamente y para poder MOSTRAR su
#     serie histórica con fines de transparencia/auditoría.
#   - DEM_MODEL_COLS (nueva) excluye 'Demings' -- es la lista que
#     alimenta el promedio ponderado, Bayes, el árbol de composición
#     Monte Carlo y winner_pool. Su columna cruda NUNCA se suma ni se
#     imputa en ningún cálculo de modelado (no se fabrica un supuesto de
#     a dónde fue a parar ese apoyo histórico, ni se cuenta como
#     "indeciso real" -- se resta explícitamente vía Retired_Mass).
#   - v7: 'Other' PODÍA representar a los candidatos menores del roster
#     vigente (Joseph, Castillo-Bach, Fernandez, Norman) -- no confirmado,
#     tratado como incertidumbre. Se intentó verificar la metodología de
#     Targoz y Change Research (las 2 encuestas de julio, 99.7% del peso)
#     y NO se encontraron los toplines/crosstabs originales publicados.
#
# =====================================================================
# RIESGO DE MAPEO DE DATOS v7 (Prioridades 1-2 de la auditoría v6, 🔴
# Crítica / 🔴 Alta) -- REQUIERE VERIFICACIÓN, NO ES ERROR CONFIRMADO
# =====================================================================
# Prioridad 1 (Change Research, Jul 9-11 2026): esta hoja registra
# Jolly=42, Foster=11, Other=8 para esa encuesta (sin fila propia para
# Joseph). Búsqueda web (requerida por política ante cualquier dato
# electoral vigente) encontró AL MENOS una fuente secundaria -- un
# resumen de mcimaps.substack.com que cita un comunicado de Change
# Research vía X/PollTracker2024, corroborado de forma independiente por
# PredictionEdge.com -- reportando esa MISMA encuesta con Jolly=42%,
# Foster=11%, Dotie Joseph=6% como cifras TOPLINE separadas. No se pudo
# acceder al crosstab/comunicado original de Change Research para
# confirmarlo de primera mano (ninguna fuente primaria disponible
# públicamente), así que el veredicto sigue siendo: RIESGO DE MAPEO DE
# DATOS -- REQUIERE VERIFICACIÓN, no un error confirmado.
#
# Prioridad 2 (Targoz Market Research, Jul 20-26 2026): pese a ser la
# encuesta de MAYOR peso del modelo, no se encontró ningún topline ni
# crosstab público independiente para verificar su fila (Jolly=47/42,
# Foster, Other=4). No hay evidencia de un error específico -- pero
# tampoco hay ninguna fuente externa que permita CONFIRMARLA, a
# diferencia de Change Research (que sí tiene al menos corroboración
# secundaria parcial). Se documenta como riesgo de datos abierto y NO
# verificable con las herramientas disponibles en esta sesión. Su
# 'Other_Minor'=4 se deja SIN TOCAR -- ninguna fuente sugiere una
# composición distinta para esta fila.
#
# =====================================================================
# DECISIÓN METODOLÓGICA v8 -- INDIVIDUALIZAR A DOTIE JOSEPH
# =====================================================================
# Hasta v7, winner_pool = ['Jolly', 'Foster'] -- los 4 candidatos menores
# de la boleta oficial (Joseph, Castillo-Bach, Fernandez, Norman) se
# trataban como un bloque agregado que NO podía ganar por diseño. El
# usuario señaló, con dos piezas de evidencia verificadas independiente-
# mente, que esa agregación ya no es la estructura más defendible para
# Joseph específicamente:
#   (1) Señal de polling propia: Change Research (Jul 9-11, 2026) le
#       asigna 6% como cifra topline separada de 'Other' (ver riesgo de
#       mapeo, Prioridad 1 arriba) -- ningún otro candidato menor tiene
#       NINGÚN dato de polling propio en ninguna encuesta de esta hoja.
#   (2) Cobertura editorial: verificado por búsqueda web (política de
#       verificar cualquier afirmación política/electoral vigente) -- "AP
#       Decision Notes: What to expect in Florida's state primary" (AP,
#       17-ago-2026, vía NBC Miami/ClickOnDetroit) nombra EXPLÍCITAMENTE
#       solo a tres de los seis demócratas calificados: "David Jolly...
#       state Rep. Dotie Joseph and... Dayna Marie Foster" -- omitiendo
#       por completo a Castillo-Bach, Fernandez y Norman. AP no usa la
#       frase "los más destacados" (esa caracterización es una lectura
#       razonable del hecho editorial, no una cita textual de AP) -- pero
#       de 6 candidatos calificados, solo esos 3 reciben mención nominal
#       en la nota de la propia AP, con Jolly además descrito con "ventaja
#       de recaudación dominante sobre el resto del campo" y Foster con
#       el respaldo del Democratic Progressive Caucus.
# Con esas dos señales (una cuantitativa, aunque de una sola encuesta; una
# cualitativa, de cobertura), se individualiza a Joseph -- pero NO a
# Castillo-Bach/Fernandez/Norman, para quienes no se encontró NINGÚN dato
# de polling propio ni mención editorial nominal (ver "¿Y los otros tres?"
# más abajo). Estructura resultante:
#   DEM_MODEL_COLS = ['Jolly', 'Foster', 'Joseph', 'Other_Minor']
#   winner_pool     = ['Jolly', 'Foster', 'Joseph']  # Other_Minor NO compite
#   Other_Minor     = Castillo-Bach + Fernandez + Norman (agregados, SIN
#                      datos propios para separarlos -- ver más abajo)
#
# EL ÚNICO CUIDADO IMPORTANTE (señalado explícitamente por el usuario):
# no se puede asumir ciegamente si el 6% de Joseph en Change Research está
# INCLUIDO dentro de Other_Minor=8 de esa fila, o si es ADICIONAL a él --
# es exactamente el mismo riesgo de mapeo de la Prioridad 1, ahora resuelto
# por CONSTRUCCIÓN (no por suposición) mediante dos escenarios de mapeo
# explícitos, seleccionables vía JOSEPH_MAPPING_SCENARIO:
#   Escenario A ('separada', BASE):  Joseph=6 se SUMA sin modificar
#     Other_Minor=8 -- no se sobrescribe ningún valor ya reportado en la
#     hoja original, solo se añade un dato nuevo. Implica que el 6% de
#     Joseph es información adicional no capturada antes: el residuo no
#     asignado de esa fila SE REDUCE en 6 pts (100-42-11-6-8=33 en vez de
#     100-42-11-8=39).
#   Escenario B ('contenida'): Joseph=6 se EXTRAE de Other_Minor=8 (queda
#     en 2) -- asume que el 8% original YA incluía a Joseph. Esto SÍ
#     modifica un valor original de la hoja a partir de una fuente
#     secundaria sin confirmación primaria, así que NUNCA se usa como
#     BASE -- solo se corre como sensibilidad explícita en la celda 6
#     ('MAPEO JOSEPH: ESCENARIO A vs. ESCENARIO B'), exactamente como pidió
#     el usuario, para cuantificar cuánto cambiaría el forecast si esta
#     asunción alternativa resultara correcta. La v7 ya mostró que una
#     perturbación de 6 pts en esta fila mueve el margen Jolly-Foster en
#     ~1.9 pts -- se espera un orden de magnitud similar aquí.
# Para Targoz (Prioridad 2) NO existe ninguna señal de Joseph -- su fila
# se deja intacta bajo ambos escenarios; 'Joseph' queda NaN ahí y se
# imputa igual que cualquier otro candidato de DEM_MODEL_COLS ausente del
# roster de una encuesta (ver imputación del residuo, más abajo). Para las
# 5 encuestas pre-retiro de Demings, Joseph no existía como candidata
# calificada en ninguna de ellas (calificó 12-jun-2026, la más reciente de
# esas 5 es Emerson, mar-2026) -- su 'Joseph' es NaN por CONSTRUCCIÓN
# temporal, no por dato faltante.
#
# ¿Y LOS OTROS TRES (Castillo-Bach, Fernandez, Norman)?
# NO se separan individualmente todavía. No se encontró NINGÚN polling
# individual, actual o histórico, para ninguno de los tres en ninguna
# fuente consultada -- ni en esta hoja ni en la búsqueda web. Asignarles
# un valor de polling inventado (p.ej. 1%/2%/3% "a ojo") sería PEOR que
# mantenerlos agrupados en 'Other_Minor' con su incertidumbre amplia: se
# fabricaría una precisión que no existe. Se mantienen agregados hasta que
# exista al menos una medición individual real para alguno de ellos.


def extract_end_date(date_str, reference_date=TODAY):
    """Misma función que el modelo republicano (v7) -- el formato de
    fecha de Dem_Primary_Polls es idéntico ('Mon D–D, YYYY', 'Mon D,
    YYYY', 'Mon D–Mon D, YYYY'), así que no requiere cambios."""
    if pd.isna(date_str):
        return pd.NaT
    s = str(date_str)
    s = re.sub(r'\[\d+\]', '', s)
    s = re.sub(r'\bthrough\b', '-', s, flags=re.IGNORECASE).strip()

    year_match = re.search(r'(\d{4})', s)
    if not year_match:
        return pd.NaT
    year = year_match.group(1)

    pieces = re.split(r'\s*[-–—]\s*', s)
    last_piece = pieces[-1]

    month_pat = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})'
    m = re.search(month_pat, last_piece)
    if m:
        mon, day = m.group(1), m.group(2)
    else:
        day_match = re.search(r'(\d{1,2})', last_piece)
        mon_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', s)
        if not (day_match and mon_match):
            return pd.NaT
        mon, day = mon_match.group(1), day_match.group(1)

    try:
        return pd.to_datetime(f"{mon} {day} {year}", format='%b %d %Y')
    except ValueError:
        return pd.NaT


# FIX v8: 'Joseph' se agrega a ambas listas -- se individualiza (ver
# DECISIÓN METODOLÓGICA v8 arriba). No existe como columna físicamente en
# la hoja Excel; se crea más abajo (tras deduplicar) a partir del único
# dato de polling disponible para ella (Change Research, bajo
# JOSEPH_MAPPING_SCENARIO). 'Other' se renombra a 'Other_Minor' arriba,
# en la ingesta -- ya NO incluye a Joseph conceptualmente (aunque, ver
# Escenario B en celda 6, su composición exacta en Change Research sigue
# siendo mapeo no confirmado).
DEM_CANDIDATE_COLS = ['Jolly', 'Foster', 'Demings', 'Joseph', 'Other_Minor']  # RAW/display -- incluye Demings (histórico)
DEM_MODEL_COLS = ['Jolly', 'Foster', 'Joseph', 'Other_Minor']  # MODELADO v8 -- Demings excluida, Joseph individualizada


def dedupe_poll_variants_dem(df):
    """
    Misma lógica de deduplicación LV > RV > promedio-de-variantes que el
    modelo republicano (v7) -- generalizada aquí a las columnas de
    candidatos DEM. Es EXACTAMENTE tan necesaria aquí como del lado REP:
    'Targoz Market Research (LV)/(RV)' y 'The Public Sentiment
    (LV)/(RV)/(A)' son la MISMA encuesta reportada para distintos
    universos, no encuestas independientes -- contarlas por separado
    infla artificialmente su peso frente a pollsters de una sola cifra.
    Con solo 10 filas de partida, este paso es incluso MÁS consecuente
    que en el modelo REP (39->46 filas): aquí reduce 10 encuestas a 7.
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
            for col in DEM_CANDIDATE_COLS:
                if col in group.columns:
                    avg_row[col] = pd.to_numeric(group[col], errors='coerce').mean()
            kept_rows.append(avg_row)

    result = pd.DataFrame(kept_rows).drop(columns=['_base_pollster', '_is_lv', '_is_rv'])
    return result.reset_index(drop=True)


n_before = len(polls_dem)
polls_dem = dedupe_poll_variants_dem(polls_dem)
print(f"Encuestas DEM antes de deduplicar variantes LV/RV/sub-muestras: {n_before}")
print(f"Encuestas DEM después (una observación por campo real):        {len(polls_dem)}")
if len(polls_dem) < 10:
    print(f"⚠️ AVISO CRÍTICO: solo {len(polls_dem)} encuestas Demócratas distintas disponibles -- "
          f"un orden de magnitud menos que las {39} del lado republicano. Toda estimación de este "
          f"modelo (medias, dispersión, kappas) es MUCHO más ruidosa e inestable que su contraparte "
          f"republicana. Los intervalos de confianza deben leerse con esa salvedad muy presente.")

# FIX v8: se crea la columna 'Joseph' -- NaN en todas las filas salvo
# Change Research (ver DECISIÓN METODOLÓGICA v8 arriba). Su único dato
# viene de la fuente secundaria corroborada (mcimaps.substack.com /
# PredictionEdge.com), NO de un topline primario -- por eso su
# incertidumbre se trata de forma explícitamente más ancha que la de
# Jolly/Foster más abajo (celda 3, NEUTRAL_PRIOR_STD_JOSEPH).
JOSEPH_MAPPING_SCENARIO = 'A'  # 'A' (BASE): Joseph=6 se SUMA sin tocar Other_Minor=8 (no sobrescribe
                               # ningún dato original). 'B' (solo sensibilidad, celda 6): Joseph=6 se
                               # EXTRAE de Other_Minor=8 (queda en 2) -- asume que ya la incluía.
polls_dem['Joseph'] = np.nan
_cr_mask_c1 = polls_dem['Poll_Source'].str.contains('Change Research', case=False, na=False)
_n_cr_c1 = int(_cr_mask_c1.sum())
assert _n_cr_c1 == 1, f"Se esperaba exactamente 1 fila de Change Research tras deduplicar, se encontraron {_n_cr_c1}."
polls_dem.loc[_cr_mask_c1, 'Joseph'] = 6.0
if JOSEPH_MAPPING_SCENARIO == 'B':
    polls_dem.loc[_cr_mask_c1, 'Other_Minor'] = polls_dem.loc[_cr_mask_c1, 'Other_Minor'] - 6.0
# JOSEPH_MAPPING_SCENARIO == 'A': Other_Minor queda intacto (8), sin tocar.
print(f"\n[FIX v8] Columna 'Joseph' creada -- dato único: Change Research (Jul 9-11 2026) = 6.0%, bajo "
      f"JOSEPH_MAPPING_SCENARIO='{JOSEPH_MAPPING_SCENARIO}' "
      f"({'sumado sin modificar Other_Minor=8' if JOSEPH_MAPPING_SCENARIO == 'A' else 'extraído de Other_Minor (8->2)'}). "
      f"Todas las demás encuestas (incluida Targoz, sin ninguna señal de Joseph) quedan con 'Joseph'=NaN -- "
      f"se imputa como cualquier otro candidato de DEM_MODEL_COLS ausente del roster de una encuesta (ver "
      f"imputación del residuo, más abajo), NO se asume 0%.")

polls_dem['Is_LV'] = polls_dem['Poll_Source'].str.contains(r'\(LV\)', na=False, flags=re.IGNORECASE)
polls_dem['Is_RV'] = polls_dem['Poll_Source'].str.contains(r'\(RV\)', na=False, flags=re.IGNORECASE)

# FIX/ADAPTACIÓN: a diferencia del lado REP (Sample 100% vacío), aquí
# Sample SÍ trae dato real en una parte de las filas. Se imputa el
# faltante con la MEDIA de los valores SÍ observados (mejor anclaje que
# una constante arbitraria, porque aquí sí hay evidencia real de qué
# tamaño de muestra usan estos pollsters) -- pero se documenta que sigue
# siendo una imputación, no un dato medido, y que mezclar filas
# reales/imputadas SÍ puede introducir un sesgo de escala si el patrón de
# missingness de Sample correlaciona con algo (p.ej. si los pollsters más
# recientes tienden a reportar Sample y los antiguos no).
polls_dem['Sample_Imputed'] = polls_dem['Sample'].isna()
_sample_mean_observed = pd.to_numeric(polls_dem['Sample'], errors='coerce').mean()
polls_dem['Sample'] = pd.to_numeric(polls_dem['Sample'], errors='coerce').fillna(_sample_mean_observed)
print(f"\nSample: {(~polls_dem['Sample_Imputed']).sum()}/{len(polls_dem)} encuestas con tamaño de muestra "
      f"real reportado; {polls_dem['Sample_Imputed'].sum()} imputadas con la media observada "
      f"({_sample_mean_observed:.0f}).")

polls_dem['End_Date'] = polls_dem['Date'].apply(extract_end_date)
polls_dem['Days_Since_Poll'] = (TODAY - polls_dem['End_Date']).dt.days

assert polls_dem['End_Date'].notna().all(), "Quedan fechas DEM sin parsear -- revisar formatos nuevos en Date."
assert (polls_dem['Days_Since_Poll'] >= 0).all(), \
    "Hay encuestas DEM con fecha futura -- revisar columna Date."

for c in DEM_CANDIDATE_COLS:
    polls_dem[c] = pd.to_numeric(polls_dem[c], errors='coerce')

# FIX/LIMITACIÓN CRÍTICA (a diferencia del modelo REP, que sí tenía una
# columna 'Undecided' real): aquí NO existe ese dato. Se infiere como
# residuo por encuesta -- 100 menos la suma de las columnas de MODELADO
# SÍ reportadas en esa fila (NaN excluido de la suma, NO tratado como 0,
# mismo principio "NaN != 0" que el resto del pipeline) MENOS
# Retired_Mass (el valor histórico de Demings, restado explícitamente --
# FIX v6, ver bloque más abajo). 'Demings' NUNCA participa de la SUMA de
# columnas de modelado (ver corrección crítica arriba), pero desde v6 su
# valor SÍ se resta aparte, para que no termine contado como indeciso
# genérico por descuido (ese era el defecto de v5, corregido más abajo).
# Sigue existiendo una limitación análoga a la de v1-v4 para 'Other'
# (ausente en 3/7 encuestas): si una encuesta no preguntó por
# 'Other' (candidatos menores), el residuo de ESA fila no es "indecisos
# reales" -- es "indecisos + el soporte real (no medido) de 'Other' en
# esa encuesta". No hay forma de corregir esto sin metadata adicional
# (qué candidatos incluyó cada encuesta en su pregunta) -- se documenta
# explícitamente en vez de tratar Unallocated_Residual como si fuera tan
# confiable como el Undecided real del modelo republicano.
# FIX v3: snapshot PRE-imputación (Jolly/Foster/Demings/Other con sus NaN
# originales intactos, más Sample/Days_Since_Poll ya calculados). Se
# conserva como punto de partida para poder reconstruir el pipeline
# completo (residuo -> promedio ponderado -> Bayes -> árbol -> early vote)
# bajo una imputación de escenario distinta (ver 'other_impute_value' en
# recompute_and_simulate_dem, celda 4) -- necesario porque en v2 cambiar
# el supuesto de un candidato faltante solo tocaba el Nivel del árbol
# correspondiente del Monte Carlo, dejando Unallocated_Residual congelado
# con la imputación BASE. Sin este snapshot no habría forma de recalcular
# el residuo desde cero para cada escenario. La columna 'Demings' se
# conserva intacta en este snapshot únicamente con fines de transparencia
# histórica -- ya no participa de ningún cálculo posterior.
polls_dem_pre_impute = polls_dem.copy()

# =====================================================================
# VERIFICACIÓN CON DATOS PROPIOS: ¿el missingness de 'Demings' coincide
# con la fecha de su retiro (5-jun-2026)? No se da por sentado el relato
# de la fuente externa -- se comprueba con un crosstab fecha-vs-NaN.
# =====================================================================
DEMINGS_SUSPENSION_DATE = pd.Timestamp('2026-06-05')

# FIX v8: fecha de calificación oficial de Joseph (ver corrección de fecha
# arriba, celda 1) -- se usa más abajo para NO imputar su valor faltante
# con la media observada en encuestas ANTERIORES a esta fecha (donde ella
# estructuralmente no podía haber sido preguntada, igual que Retired_Mass
# es 0-por-construcción para Demings post-retiro, no "dato faltante").
JOSEPH_QUALIFICATION_DATE = pd.Timestamp('2026-06-12')

_demings_check = polls_dem[['Poll_Source', 'Date', 'End_Date', 'Demings']].copy()
_demings_check['Post_Suspension'] = _demings_check['End_Date'] > DEMINGS_SUSPENSION_DATE
_demings_check['Demings_NaN'] = _demings_check['Demings'].isna()
_demings_crosstab = pd.crosstab(_demings_check['Demings_NaN'], _demings_check['Post_Suspension'])
print("\n--- VERIFICACIÓN: ¿Demings-NaN coincide con encuestas posteriores a su retiro (5-jun-2026)? ---")
print(_demings_check[['Poll_Source', 'End_Date', 'Demings', 'Post_Suspension']].to_string(index=False))
print(_demings_crosstab)
_clean_split = (
    _demings_crosstab.shape == (2, 2)
    and _demings_crosstab.loc[False, True] == 0
    and _demings_crosstab.loc[True, False] == 0
)
if _clean_split:
    print("CONFIRMADO con datos propios del notebook: el missingness de 'Demings' es un split TEMPORAL "
          "perfecto -- TODAS las encuestas que la reportan son anteriores al 5-jun-2026 y TODAS las que no "
          "la reportan son posteriores. Esto no es un patrón de missingness genérico/aleatorio de roster "
          "incompleto (como sí lo es 'Other', ver más abajo): es la firma exacta de una candidata que dejó "
          "de estar en boleta a partir de una fecha concreta. Confirma que excluirla del modelado (en vez de "
          "imputar/tratarla como missing-at-random) es el tratamiento correcto para estos datos.")
else:
    print("⚠️ AVISO: el split temporal NO es perfecto con los datos actuales -- revisar manualmente antes de "
          "asumir que el missingness de Demings se explica enteramente por la fecha de su retiro.")

# =====================================================================
# CORRECCIÓN v6 -- CRÍTICA #1 de la auditoría v5: "no convertir
# Retired_Mass pre-Demings en Unallocated_Residual"
# =====================================================================
# v5 excluía a Demings de la RESTA que define el residuo (usaba solo
# DEM_MODEL_COLS = Jolly/Foster/Other), lo cual tenía un efecto colateral
# no intencionado: su apoyo histórico medido (donde existía, en 5/7
# encuestas) terminaba DENTRO del residuo, inflándolo artificialmente --
# 20 puntos de Demings medida y real se contaban como "no sabe/no
# contesta". El propio v5 lo documentaba, pero documentarlo no lo hacía
# correcto: un valor MEDIDO no es lo mismo que un valor DESCONOCIDO.
#
# FIX v6: se separan ambos conceptos.
#   - 'Retired_Mass': el apoyo histórico de Demings donde se reportó (su
#     valor crudo). Es puramente informativo/de auditoría -- NUNCA se sube
#     a ningún promedio ponderado, Bayes o árbol de composición.
#   - 'Unallocated_Residual': ahora se calcula restando Retired_Mass
#     explícitamente (fillna(0) porque en las encuestas post-retiro
#     Demings NO es "dato faltante" sino "0% por definición, no está en
#     esa boleta" -- semánticamente distinto del missingness genuino de
#     'Other', que SÍ se sigue imputando con la media observada). Esto
#     hace que el residuo vuelva a representar lo que dice representar:
#     indeciso genuino + roster no itemizado, SIN el apoyo ya medido de
#     una candidata retirada.
polls_dem['Retired_Mass'] = polls_dem['Demings']

polls_dem['Unallocated_Residual_Naive'] = (
    100 - polls_dem[DEM_MODEL_COLS].sum(axis=1, skipna=True) - polls_dem['Retired_Mass'].fillna(0.0)
)

# FIX v2 (corrección prioritaria de la auditoría v1 -- el hallazgo más
# importante de esa ronda, sigue vigente para 'Other'): tratar el residuo
# NAIVE como si fuera enteramente indeciso real sobreestima el indeciso en
# las encuestas con roster incompleto, porque ese residuo también absorbe
# el soporte NO MEDIDO del candidato de modelado que esa encuesta no
# preguntó (hoy, solo 'Other' puede faltar -- Jolly y Foster están
# presentes en las 7). Se IMPUTA el valor de cualquier candidato de
# MODELADO ausente del roster de una encuesta con el promedio simple
# observado en las encuestas que sí lo reportan, y el residuo se calcula
# DESPUÉS de esa imputación. 'Unallocated_Residual_Naive' queda disponible
# para comparar la magnitud de esta corrección en todo momento.
_impute_means = {c: polls_dem[c].mean() for c in DEM_MODEL_COLS}
_imputed_cols_for_residual = pd.DataFrame(
    {c: polls_dem[c].fillna(_impute_means[c]) for c in DEM_MODEL_COLS}
)
# FIX v8: Joseph no existía como candidata calificada antes de
# JOSEPH_QUALIFICATION_DATE (12-jun-2026) -- para esas encuestas, su
# ausencia NO es "missingness genuino de roster incompleto" (el caso que
# la imputación de arriba corrige, con el promedio de las encuestas que sí
# la reportan) sino "estructuralmente 0%, no estaba en boleta", el MISMO
# principio que 'Retired_Mass'.fillna(0.0) para Demings post-retiro más
# abajo. Imputar el promedio general (dominado por su única medición,
# Change Research=6%) en esas encuestas pre-calificación fabricaría un
# supuesto de que Joseph tenía ~6% de soporte ANTES de existir como
# candidata -- se sobrescribe explícitamente con 0 para esas filas.
_joseph_pre_qualification = polls_dem['End_Date'] <= JOSEPH_QUALIFICATION_DATE
_imputed_cols_for_residual.loc[_joseph_pre_qualification, 'Joseph'] = 0.0
polls_dem['Unallocated_Residual'] = (
    100 - _imputed_cols_for_residual.sum(axis=1) - polls_dem['Retired_Mass'].fillna(0.0)
).clip(lower=0)

_polls_missing_other = polls_dem['Other_Minor'].isna().sum()
_polls_with_demings_history = polls_dem['Retired_Mass'].notna().sum()
_naive_mean_illus = polls_dem['Unallocated_Residual_Naive'].mean()
_imputed_mean_illus = polls_dem['Unallocated_Residual'].mean()
print(f"\n⚠️ AVISO CRÍTICO (limitación SIN equivalente en el modelo republicano): no existe columna "
      f"'Undecided' real en las encuestas DEM. De las {len(polls_dem)} encuestas, {_polls_missing_other} "
      f"no reportan 'Other_Minor' -- un residuo NAIVE (100% - suma de columnas de modelado reportadas) confunde "
      f"indeciso real con soporte no medido del candidato excluido del roster. FIX v2: se imputa el "
      f"candidato de modelado ausente con el promedio simple de las encuestas que sí lo reportan ANTES de "
      f"calcular el residuo -- el residuo promedio (simple, sin ponderar) pasa de {_naive_mean_illus:.1f}% "
      f"(naive) a {_imputed_mean_illus:.1f}% (imputado). FIX v6 (corrección crítica de la auditoría v5): "
      f"{_polls_with_demings_history} de {len(polls_dem)} encuestas reportan el histórico de Demings "
      f"('Retired_Mass') -- ese valor AHORA SÍ se resta explícitamente de 100% al calcular el residuo (antes "
      f"de v6 no se restaba, y su apoyo medido se contaba por error como indeciso). Retired_Mass es "
      f"puramente informativo: nunca entra a ningún promedio ponderado, Bayes o árbol de composición. "
      f"Sigue siendo una aproximación, no un dato medido, y se documenta como tal; "
      f"'Unallocated_Residual_Naive' queda disponible para comparar en todo momento.")

# =====================================================================
# FIX v6 (segunda mitad de la corrección crítica #1): columnas de
# MODELADO (usadas en el promedio ponderado que alimenta a Bayes) para
# Jolly/Foster/Other_Minor. En las encuestas PRE-retiro (Demings reportada), el
# valor crudo de Jolly/Foster/Other_Minor representa "% del total de la
# muestra cuando Demings TAMBIÉN competía por una porción del mismo
# pastel" -- una base distinta a la de las encuestas post-retiro, donde
# ese mismo % ya no compite con nadie por esa porción. Para que las
# encuestas antiguas aporten información sobre la POSICIÓN RELATIVA de
# los candidatos sobrevivientes (no distorsionada por cuánto se llevaba
# Demings), se renormalizan a J* = J/(J+F+O), F* = F/(J+F+O),
# O* = O/(J+F+O) -- ÚNICAMENTE cuando Jolly, Foster y Other_Minor están los
# TRES presentes en esa fila (una "tripleta completa"). Si falta alguno
# de los tres (le pasa a 4 de las 5 encuestas pre-retiro: falta Foster
# en Targoz-feb/Mason-Dixon/PPP), renormalizar exigiría además imputar el
# denominador -- eso compondría dos aproximaciones en cascada sin ganancia
# clara sobre simplemente dejar el valor crudo. En esos casos se deja el
# valor SIN TOCAR (igual que en v5), y el dropna() de weighted_average()
# sigue excluyendo esa fila de ese candidato en particular, como siempre.
#
# LIMITACIÓN DOCUMENTADA (no resuelta, señalada explícitamente en vez de
# ocultada): esta renormalización solo puede aplicarse hoy a UNA encuesta
# (Emerson College, mar-2026) -- la única con tripleta Jolly/Foster/Other_Minor
# completa entre las 5 pre-retiro. Además, introduce una base distinta
# entre encuestas renormalizadas (suman 100% entre J/F/O, sin indeciso
# propio) y encuestas post-retiro sin renormalizar (suman <100%, con su
# propio indeciso real incluido) -- mezclarlas en un mismo promedio
# ponderado no es perfectamente homogéneo. Dado que Emerson pesa <0.3% a
# half_life=14 (y hasta ~3.4% a half_life=30, ver sensibilidad estructural
# celda 6), el efecto numérico de esta inconsistencia es acotado pero NO
# nulo -- se documenta en vez de asumir que es irrelevante.
_complete_triple = polls_dem[['Jolly', 'Foster', 'Other_Minor']].notna().all(axis=1)
_has_retired_mass = polls_dem['Retired_Mass'].notna()
_renorm_mask = _complete_triple & _has_retired_mass
_survivor_denom = polls_dem['Jolly'] + polls_dem['Foster'] + polls_dem['Other_Minor']
# FIX v8: 'Joseph' se incluye en este loop también (no en el denominador
# -- la renormalización sigue siendo J/(J+F+Om), Joseph nunca compitió en
# esas 5 encuestas pre-retiro, ver DECISIÓN METODOLÓGICA v8) simplemente
# para que exista 'Joseph_ModelInput' de forma consistente con
# Jolly/Foster/Other_Minor -- en la práctica es un passthrough puro: es
# NaN en las filas pre-retiro (Joseph no existía) y su valor crudo en la
# única fila donde sí hay dato (Change Research, post-retiro, fuera de
# _renorm_mask).
for _c in ['Jolly', 'Foster', 'Joseph', 'Other_Minor']:
    polls_dem[f'{_c}_ModelInput'] = np.where(
        _renorm_mask, polls_dem[_c] / _survivor_denom * 100.0, polls_dem[_c]
    )
_n_renorm = int(_renorm_mask.sum())
print(f"\n[Renormalización 'sobreviviente' -- FIX v6] {_n_renorm}/{len(polls_dem)} encuesta(s) pre-retiro "
      f"con tripleta Jolly/Foster/Other_Minor completa se renormalizaron a J*=J/(J+F+O) etc. para aportar solo "
      f"su posición RELATIVA entre candidatos vigentes, sin la distorsión de cuánto se llevaba Demings. Las "
      f"demás encuestas (falta algún dato de la tripleta, o son post-retiro) usan su valor crudo sin tocar.")
if _n_renorm > 0:
    print(polls_dem.loc[_renorm_mask, ['Poll_Source', 'Jolly', 'Foster', 'Joseph', 'Other_Minor', 'Retired_Mass',
                                        'Jolly_ModelInput', 'Foster_ModelInput', 'Joseph_ModelInput', 'Other_Minor_ModelInput']]
          .to_string(index=False))

# FIX v7 (Prioridad 3 de la auditoría v6, 🟠 Media -- "no usaría una
# encuesta antigua simultáneamente para: estimar composición condicional
# entre sobrevivientes y nivel absoluto del residuo"): una fila renormalizada
# ya reexpresó Jolly/Foster/Other_Minor en la escala "100% = solo sobrevivientes",
# una escala DISTINTA a la escala cruda ("100% = muestra completa incluyendo
# a Demings") en la que se calculó Unallocated_Residual arriba. Dejar que esa
# misma fila siga aportando su Unallocated_Residual crudo al promedio
# ponderado de current_unallocated_avg mezclaría dos bases no homogéneas: la
# composición relativa ya excluye a Demings por construcción (denominador
# J+F+O), pero el residuo crudo todavía la trata como si su masa no se
# hubiera reasignado. Se anula (NaN) el residuo SOLO de las filas
# renormalizadas -- weighted_average() ya excluye NaN vía dropna(), así que
# esas filas simplemente dejan de opinar sobre el NIVEL del indeciso (para
# el que además son la fuente menos fiable: son las únicas 100%-completas en
# J/F/O, así que su residuo naive-imputado tiende a subestimar cuánto
# indeciso real había en ESA encuesta específica) sin dejar de aportar su
# señal de POSICIÓN RELATIVA vía *_ModelInput.
if _n_renorm > 0:
    _resid_antes = polls_dem.loc[_renorm_mask, 'Unallocated_Residual'].round(2).tolist()
    polls_dem.loc[_renorm_mask, 'Unallocated_Residual'] = np.nan
    print(f"\n[FIX v7 -- anti scale-mixing] Unallocated_Residual de la(s) {_n_renorm} fila(s) renormalizada(s) "
          f"se anula (antes: {_resid_antes}) para no mezclar su escala 'solo sobrevivientes' (ModelInput) con "
          f"la escala cruda del residuo. Esa(s) fila(s) sigue(n) aportando posición relativa vía "
          f"*_ModelInput; deja(n) de aportar nivel de indeciso.")

print("\nConsolidando Voto Anticipado y Demográficos por Condado (Demócrata)...")

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

county_master_dem = ev_summary[['County', 'Reg_Dem', 'Cast_Dem', 'Dem_Turnout_Pct']].merge(
    demo_subset, on='County', how='left', validate='one_to_one'
)

county_master_dem = county_master_dem.merge(
    turnout_hist[['County', 'Avg_Pct_Gov_Primaries', 'Pct_2022', 'Pct_2018', 'Diff_2022_vs_2018']],
    on='County', how='left', validate='one_to_one'
)

assert county_master_dem['Pct_2018'].notna().all(), \
    "Hay condados sin match en el histórico de turnout -- revisar nombres de condado."

# FIX/ADAPTACIÓN CLAVE frente al modelo REP: allá 2022 se excluyó porque
# NO hubo primaria republicana de gobernador disputada (Total_Rep_Votes=0
# en todos los condados). Del lado DEMÓCRATA, 2022 SÍ fue una primaria
# real y competitiva (Crist vs. Fried vs. Daniel vs. Willis). Se verifica
# aquí con los datos propios del notebook, igual que se hizo del lado REP.
try:
    hist_2018 = pd.read_excel('Florida_Governor_Primaries_2018_2022.xlsx', sheet_name='Governor_Primary_2018')
    hist_2022 = pd.read_excel('Florida_Governor_Primaries_2018_2022.xlsx', sheet_name='Governor_Primary_2022')

    dem_votes_2018 = hist_2018['Total_Dem_Votes'].sum()
    dem_votes_2022 = hist_2022['Total_Dem_Votes'].sum()

    print("\n--- AUDITORÍA: ¿2022 es un punto de comparación válido para DEM? ---")
    print(f"Votos totales DEM primaria de gobernador, 2018 (todo el estado): {dem_votes_2018:,.0f}")
    print(f"Votos totales DEM primaria de gobernador, 2022 (todo el estado): {dem_votes_2022:,.0f}")
    if dem_votes_2018 > 0 and dem_votes_2022 > 0:
        print("CONFIRMADO con datos propios del notebook: AMBOS años tuvieron primaria demócrata de "
              "gobernador real y competitiva -- a diferencia del lado republicano (donde 2022 se excluyó "
              "por Total_Rep_Votes=0), aquí SÍ es razonable usar el promedio de ambos años "
              "(Avg_Pct_Gov_Primaries) como base de turnout esperado, en vez de un solo año.")

    # Mismo chequeo de "¿Reg_2018 es un padrón general o específico del "
    # partido?" que en el modelo REP, aquí contra Reg_Dem.
    reg_check = ev_summary[['County', 'Reg_Total', 'Reg_Dem']].merge(
        turnout_hist[['County', 'Reg_2018']], on='County', validate='one_to_one'
    )
    corr_vs_total = reg_check['Reg_2018'].corr(reg_check['Reg_Total'])
    corr_vs_dem = reg_check['Reg_2018'].corr(reg_check['Reg_Dem'])
    ratio_vs_dem = (reg_check['Reg_2018'] / reg_check['Reg_Dem']).mean()
    print(f"\n¿Reg_2018 es un padrón demócrata o general? Reg_2018 correlaciona {corr_vs_total:.3f} con "
          f"el padrón TOTAL 2026 vs. {corr_vs_dem:.3f} con el padrón SOLO-DEM 2026 (Reg_2018 es en "
          f"promedio ~{ratio_vs_dem:.1f}x el padrón demócrata actual).")
    print("CONCLUSIÓN: igual que del lado republicano, Reg_2018/Pct_2018/Pct_2022 son cifras de TODOS "
          "los partidos, no específicas de demócratas -- el turnout esperado de más abajo asume que "
          "los demócratas participan a la misma TASA que el electorado general. A diferencia del lado "
          "REP, aquí sí se puede promediar 2018+2022 (ambos años válidos), pero la limitación de fondo "
          "'tasa general, no de partido' es la MISMA en ambos modelos.")
except FileNotFoundError:
    print("\n(No se encontró Florida_Governor_Primaries_2018_2022.xlsx -- se omite la auditoría cruzada.)")

print("\n--- RESUMEN DE DATOS LIMPIOS (DEM) ---")
print(f"Encuestas procesadas: {len(polls_dem)}")
print(f"Rango de fechas de encuestas: {polls_dem['End_Date'].min().strftime('%Y-%m-%d')} a "
      f"{polls_dem['End_Date'].max().strftime('%Y-%m-%d')}")
print(f"Condados consolidados: {len(county_master_dem)}")


# =====================================================================
# CELDA "2. Ponderación (Demócrata)" -- NUEVA v1
# =====================================================================
print("\nCalculando promedios ponderados de encuestas DEM (Time-Decay)...")

# FIX/DECISIÓN METODOLÓGICA: house_effects vacío para el modelo DEM.
# Los ajustes manuales del modelo REP (Targoz +1.5/-0.5, Change Research
# (D) -2.0/+1.0) fueron estimados/asumidos EN EL CONTEXTO de esos
# candidatos y esa contienda republicana -- no hay base para asumir que
# el mismo sesgo numérico aplica a cómo esos pollsters miden a
# Jolly/Foster en una primaria demócrata. Reusar esos números
# aquí sería inventar un dato, no adaptar un fix. Se deja el mecanismo
# (house_effects_dem) vacío pero funcional, para que se pueda poblar si
# en el futuro hay evidencia real de sesgo por encuestadora específica a
# esta contienda.
house_effects_dem = {}


def clean_pollster_name(pollster):
    name = re.sub(r'\s*\((LV|RV)\)', '', pollster, flags=re.IGNORECASE)
    name = re.sub(r'\s*\[\d+\]', '', name)
    return name.strip()


def apply_house_effects(row, candidate, effects_dict, value_col=None):
    """FIX v6: acepta 'value_col' explícito -- por defecto usa la columna
    cruda 'candidate', pero se le pasa '{candidate}_ModelInput' para que
    los house effects (hoy vacíos, pero el mecanismo debe seguir siendo
    correcto si se poblaran) se apliquen sobre el valor YA renormalizado
    (ver corrección crítica #1 de la auditoría v5, celda 1), no sobre el
    crudo sin corregir por la distorsión de Demings."""
    pollster = row['Poll_Source']
    col = value_col if value_col is not None else candidate
    base_val = row[col]
    if pd.isna(base_val):
        return np.nan
    pollster_clean = clean_pollster_name(pollster)
    bias = effects_dict.get(pollster_clean, {}).get(candidate, 0.0)
    return base_val - bias


# FIX v8: 'Joseph' se agrega a este loop -- se individualiza (ver
# DECISIÓN METODOLÓGICA v8, celda 1). Demings sigue excluida.
for cand in ['Jolly', 'Foster', 'Joseph']:
    polls_dem[f'{cand}_Adj'] = polls_dem.apply(
        lambda r, cand=cand: apply_house_effects(r, cand, house_effects_dem, value_col=f'{cand}_ModelInput'),
        axis=1
    )

half_life = 14  # MISMO hiperparámetro asumido que el modelo REP (v7) -- no hay evidencia para elegir otro
decay_rate = np.log(2) / half_life
polls_dem['Poll_Weight'] = polls_dem['Sample'] * np.exp(-decay_rate * polls_dem['Days_Since_Poll'])

# AVISO CRÍTICO NUEVO (sin equivalente exacto en la severidad del lado
# REP): con solo 7 encuestas DEM tras deduplicar, un rango de fechas
# mucho más disperso que el REP (22 a 257 días de antigüedad) y
# half_life=14 (el MISMO valor asumido para REP, no recalibrado), el
# decaimiento exponencial deja prácticamente TODO el peso en las 1-2
# encuestas más recientes -- las 5 encuestas más antiguas contribuyen casi
# nada al promedio ponderado. Se verifica y documenta explícitamente para
# que no se lea el "promedio de 7 encuestas" como si tuviera la robustez
# de promediar 7 observaciones independientes.
_weight_share = polls_dem[['Poll_Source', 'Days_Since_Poll', 'Poll_Weight']].copy()
_weight_share['Weight_Share_%'] = _weight_share['Poll_Weight'] / _weight_share['Poll_Weight'].sum() * 100
_weight_share = _weight_share.sort_values('Days_Since_Poll')
print("\n⚠️ AVISO CRÍTICO: con half_life=14 días (mismo valor que el modelo REP) y encuestas DEM que van "
      "de 22 a 257 días de antigüedad, el peso NO se reparte uniformemente entre las 7 encuestas:")
print(_weight_share.to_string(index=False))
print(f"Las 2 encuestas más recientes concentran {_weight_share['Weight_Share_%'].nlargest(2).sum():.1f}% "
      f"del peso total -- el modelo DEM es, en la práctica, un modelo de 2 encuestas con 5 encuestas de "
      f"adorno estadístico. Esto se prueba explícitamente en la sensibilidad de half_life más abajo, "
      f"donde el efecto es mucho mayor que en el modelo REP.")


def weighted_average(df, value_col, weight_col):
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    return np.average(subset[value_col], weights=subset[weight_col])


def poll_dispersion(df, value_col, weight_col, mean_val_pct):
    """Dispersión ponderada ENTRE encuestas -- MISMA advertencia que el
    modelo REP: proxy, no error estándar calibrado. Con n=7 (y a veces
    menos por candidato, ver abajo) este proxy es todavía más ruidoso
    que en el modelo REP (n=39)."""
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    variance = np.average((subset[value_col] - mean_val_pct) ** 2, weights=subset[weight_col])
    return np.sqrt(variance)


# FIX/SIMPLIFICACIÓN ESTRUCTURAL frente al modelo REP: allá, 'Other_Named'
# combinaba DOS columnas (Renner+Other) y eso exigía la corrección de
# "no tratar el componente faltante como cero" (usar solo encuestas
# pareadas). Aquí, 'Other' es UNA sola columna de origen -- exactamente
# igual que Jolly/Foster, cada una con su propio dropna(). No hace falta
# reconstruir el fix de "paired subset" porque no hay ninguna suma de dos
# columnas distintas en ningún punto de este pipeline DEM.
#
# FIX v6: se usa '{cand}_ModelInput' (renormalizado para la única encuesta
# pre-retiro con tripleta completa, ver celda 1) en vez del crudo -- así
# la corrección de la auditoría v5 realmente llega hasta el promedio
# ponderado, no solo hasta el residuo.
# FIX v8: JOSEPH_MIN_POLL_STD -- piso explícito de incertidumbre de DATOS
# para Joseph. poll_dispersion() mide dispersión ENTRE encuestas; con
# n=1 (Change Research es la única que la reporta) esa dispersión es
# matemáticamente 0 -- una sola observación no tiene varianza muestral.
# Tratar eso como "certeza total" sería exactamente lo opuesto de la
# realidad (mínima evidencia, máxima incertidumbre) y haría que el
# posterior Bayesiano colapsara sobre un único punto de una fuente
# secundaria no confirmada (ver riesgo de mapeo, celda 1). Se fija un piso
# deliberadamente ANCHO -- más ancho que la dispersión típica observada
# entre las 7 encuestas de Jolly/Foster (~2-3 pts) -- para reflejar
# honestamente cuánta menos evidencia hay detrás de esta cifra.
JOSEPH_MIN_POLL_STD = 8.0  # puntos porcentuales
current_polling_avg = {}
current_polling_std = {}
current_polling_n = {}
for cand in ['Jolly', 'Foster', 'Joseph']:  # v8: Joseph individualizada, ver celda 1. Demings excluida.
    mean_pct = weighted_average(polls_dem, f'{cand}_Adj', 'Poll_Weight')
    std_pct = poll_dispersion(polls_dem, f'{cand}_Adj', 'Poll_Weight', mean_pct)
    current_polling_n[cand] = polls_dem[cand].notna().sum()
    if cand == 'Joseph' and current_polling_n[cand] <= 1:
        std_pct = max(std_pct, JOSEPH_MIN_POLL_STD)
    current_polling_avg[cand] = mean_pct / 100.0
    current_polling_std[cand] = std_pct / 100.0

other_minor_avg = weighted_average(polls_dem, 'Other_Minor_ModelInput', 'Poll_Weight') / 100.0
other_minor_std = poll_dispersion(polls_dem, 'Other_Minor_ModelInput', 'Poll_Weight', other_minor_avg * 100) / 100.0
other_minor_n = polls_dem['Other_Minor'].notna().sum()

current_unallocated_avg = weighted_average(polls_dem, 'Unallocated_Residual', 'Poll_Weight') / 100.0
unallocated_std = poll_dispersion(polls_dem, 'Unallocated_Residual', 'Poll_Weight', current_unallocated_avg * 100) / 100.0

# SOLO TRANSPARENCIA HISTÓRICA -- no participa de ningún cómputo posterior
# (Bayes, árbol de composición, winner_pool). Se calcula y se muestra
# únicamente para que el lector pueda ver qué tan grande era el soporte
# medido de Demings antes de su retiro, sin que ese número se use en el
# forecast vigente.
_demings_hist_avg = weighted_average(polls_dem, 'Demings', 'Poll_Weight')
_demings_hist_n = polls_dem['Demings'].notna().sum()

print("\nPromedio Ponderado Actual DEM (n = encuestas que reportan esa columna, de 7 totales):")
for k, v in current_polling_avg.items():
    _floor_note = " -- PISO APLICADO (n=1, ver JOSEPH_MIN_POLL_STD)" if k == 'Joseph' and current_polling_n[k] <= 1 else ""
    print(f"{k}: {v*100:.2f}% (dispersión entre encuestas: {current_polling_std[k]*100:.2f} pts, n={current_polling_n[k]}{_floor_note})")
print(f"Other_Minor (Castillo-Bach + Fernandez + Norman agregados, sin datos propios para separarlos -- ver "
      f"nota crítica celda 1): {other_minor_avg*100:.2f}% "
      f"(dispersión: {other_minor_std*100:.2f} pts, n={other_minor_n})")
print(f"Unallocated_Residual (INFERIDO, ver aviso crítico arriba -- NO es dato reportado): "
      f"{current_unallocated_avg*100:.2f}% (dispersión: {unallocated_std*100:.2f} pts)")
print(f"[SOLO HISTÓRICO, fuera del modelo] Demings (retirada 5-jun-2026, NO compite): "
      f"{_demings_hist_avg:.2f}% en las {_demings_hist_n} encuestas pre-retiro que la reportaron -- este "
      f"valor NO se usa en ningún cálculo posterior, se muestra solo con fines de auditoría/transparencia.")

_pool_sum_check = sum(current_polling_avg.values()) + other_minor_avg + current_unallocated_avg
print(f"\n[Diagnóstico] Suma cruda Jolly+Foster+Joseph+Other_Minor+Unallocated_Residual: {_pool_sum_check*100:.2f}% "
      f"(gap vs. 100%: {(_pool_sum_check-1)*100:+.2f} pts -- cada término viene de un subconjunto de "
      f"encuestas potencialmente distinto, mismo fenómeno ya documentado en el modelo REP).")


# =====================================================================
# CELDA "3. Modelado Ensemble (Demócrata)" -- NUEVA v1
# =====================================================================
print("\nIniciando Ensamble Bayesiano DEM: Priors neutros + Encuestas...")

# FIX/DECISIÓN METODOLÓGICA CRÍTICA: el modelo REP tenía subjective_priors
# reales (aunque subjetivos) -- un juicio de partida del analista sobre
# fundamentales (45/15/10 para Donalds/Collins/Fishback). NO existe un
# equivalente para Jolly/Foster en ningún archivo de esta carpeta --
# inventar números "a ojo" para el lado demócrata sería peor que no tener
# prior, porque parecería tan fundamentado como el REP sin serlo. En su
# lugar, se usa un prior NEUTRO: centrado en el promedio de encuestas de
# CADA candidato (no jala la media hacia ningún lado) con una desviación
# estándar deliberadamente MUY ancha (30 pts) para que tenga precisión
# casi nula frente a los datos -- el posterior resultante es, por
# construcción, prácticamente idéntico al promedio de encuestas puro. Se
# mantiene la arquitectura Bayesiana (por paridad con el modelo REP y por
# si en el futuro se dispone de fundamentales reales), pero hoy no aporta
# información adicional -- ES UNA DIFERENCIA ESTRUCTURAL EXPLÍCITA frente
# al modelo republicano, no un descuido.
#
# v5: solo Jolly/Foster -- Demings excluida del pool de modelado (ver
# nota crítica en celda 1).
# FIX v8: Joseph se agrega al pool -- vuelve a ser un Nivel 2 de 3
# categorías (Dirichlet), como en v1-v4 (entonces Jolly/Foster/Demings),
# ahora Jolly/Foster/Joseph (ver celda 4). El prior neutro de Joseph usa
# el MISMO NEUTRAL_PRIOR_STD=0.30 que Jolly/Foster -- no hace falta
# ensancharlo aparte, porque su incertidumbre real ya entra por el lado de
# los DATOS (JOSEPH_MIN_POLL_STD=8 pts en la celda 2, ~4x más ancho que la
# dispersión típica de Jolly/Foster) -- con un prior de precisión casi
# nula (std=0.30) frente a cualquier data_std, el posterior de Joseph
# queda dominado por su propio data_std ancho, exactamente el efecto
# buscado: bayesian_update(prior_std=0.30, data_std=0.08) da un posterior
# de ~7.7 pts, varias veces más ancho que el de Jolly/Foster (~2 pts) --
# sin necesidad de tocar el prior.
NEUTRAL_PRIOR_STD = 0.30
subjective_priors_dem = {
    cand: {'mean': current_polling_avg[cand], 'std': NEUTRAL_PRIOR_STD}
    for cand in ['Jolly', 'Foster', 'Joseph']
}

polling_data_dem = {
    cand: {'mean': current_polling_avg[cand], 'std': current_polling_std[cand]}
    for cand in subjective_priors_dem.keys()
}


def bayesian_update(prior_mean, prior_std, data_mean, data_std):
    """Misma función que el modelo REP -- misma limitación documentada
    (Normales independientes por candidato, no impone p_J+p_F+p_otros=1
    en esta capa; la restricción de composición se aplica más abajo, en
    el árbol Dirichlet/Beta del Monte Carlo)."""
    prior_precision = 1.0 / (prior_std ** 2)
    data_precision = 1.0 / (data_std ** 2)
    posterior_precision = prior_precision + data_precision
    posterior_mean = ((prior_mean * prior_precision) + (data_mean * data_precision)) / posterior_precision
    posterior_std = np.sqrt(1.0 / posterior_precision)
    return posterior_mean, posterior_std


ensemble_posteriors_dem = {}
for candidate in subjective_priors_dem.keys():
    p_mean = subjective_priors_dem[candidate]['mean']
    p_std = subjective_priors_dem[candidate]['std']
    d_mean = polling_data_dem[candidate]['mean']
    d_std = polling_data_dem[candidate]['std']
    post_mean, post_std = bayesian_update(p_mean, p_std, d_mean, d_std)
    ensemble_posteriors_dem[candidate] = {'mean': post_mean, 'std': post_std}

total_assigned_dem = sum(v['mean'] for v in ensemble_posteriors_dem.values())
unallocated_pool_dem = current_unallocated_avg

# FIX/DECISIÓN METODOLÓGICA: undecided_allocation del modelo REP era un
# número fijo, elegido a mano (60/25/15), presumiblemente ya proporcional
# al polling inicial de Donalds/Collins/Fishback. Sin un prior subjetivo
# real de dónde viene ese 60/25/15 para Dem, se deriva aquí
# explícitamente en PROPORCIÓN al polling actual (posterior Bayesiano)
# de cada candidato -- método más transparente y reproducible que
# "elegir a mano", aunque conceptualmente sigue siendo un supuesto (no
# hay evidencia de que los indecisos vayan a repartirse en esa
# proporción exacta).
#
# ACLARACIÓN v6 (auditoría v5, puntos 4-5), actualizada v8: "proporcional
# al polling actual" aquí significa proporcional SOLO a los candidatos del
# pool de Bayes -- 'ensemble_posteriors_dem' (Other_Minor NUNCA entra a
# Bayes, ver celda 3 más arriba). Hasta v7 el pool era {Jolly, Foster}; en
# v8 es {Jolly, Foster, Joseph} -- el residual de indecisos ahora SÍ puede
# fluir hacia Joseph (proporcional a su posterior, que a su vez ya es
# ancho por JOSEPH_MIN_POLL_STD), aunque Other_Minor sigue excluido por
# diseño -- ver la sensibilidad 'undecided_a_other' en la celda 6, que
# explora justamente relajar ese supuesto (0/10/25/50% del residual hacia
# Other_Minor).
_alloc_base = {c: ensemble_posteriors_dem[c]['mean'] for c in ensemble_posteriors_dem}
_alloc_total = sum(_alloc_base.values())
undecided_allocation_dem = {c: v / _alloc_total for c, v in _alloc_base.items()}
print(f"\nReparto de indecisos DEM (proporcional a Jolly:Foster:Joseph -- Other_Minor excluido por diseño, ver "
      f"aclaración arriba; NO elegido a mano como en el modelo REP): " +
      ", ".join(f"{c} {v*100:.1f}%" for c, v in undecided_allocation_dem.items()))

final_ensemble_estimates_dem = {}
print("\nResultados del Modelo Ensemble DEM (Capa 1 + Capa 2 + Indecisos):")
print("-" * 60)
for candidate, post in ensemble_posteriors_dem.items():
    final_mean = post['mean'] + (unallocated_pool_dem * undecided_allocation_dem[candidate])
    final_ensemble_estimates_dem[candidate] = {
        'mean': final_mean,
        'std': post['std']
    }
    print(f"{candidate}:")
    print(f"  └─ Prior neutro (= encuestas, std ancho):  {subjective_priors_dem[candidate]['mean']*100:.1f}%")
    print(f"  └─ Encuestas (Data):                        {polling_data_dem[candidate]['mean']*100:.1f}%")
    print(f"  └─ Point estimate (previo a Monte Carlo, incluye asignación puntual de indecisos): "
          f"{final_mean*100:.1f}% (std posterior pre-indecisos, NO es la incertidumbre final: "
          f"{post['std']*100:.1f} pts -- ver 'RANGOS PROBABLES DE VOTO' más abajo para el IC95% "
          f"condicional del Monte Carlo, NO un intervalo calibrado electoralmente)")


# =====================================================================
# CELDA "4. Simulación (Demócrata)" -- NUEVA v1
# =====================================================================
import numpy as np
import pandas as pd

print("\nEjecutando Simulación Monte Carlo DEM (10,000 iteraciones)...")

total_early_votes_dem = float(
    ev_statewide.loc[ev_statewide['Metric'] == 'Already Cast - Democrat', 'Value'].iloc[0]
)

# FIX/ADAPTACIÓN: a diferencia del modelo REP (solo Pct_2018 válido), aquí
# SÍ se promedian 2018 y 2022 -- ambos años confirmados como primarias
# demócratas reales y competitivas arriba. Avg_Pct_Gov_Primaries ya viene
# precalculado en turnout_hist como el promedio simple (Pct_2018+Pct_2022)/2
# por condado.
total_expected_turnout_dem = float(
    (county_master_dem['Reg_Dem'] * county_master_dem['Avg_Pct_Gov_Primaries'] / 100.0).sum()
)

# [Diagnóstico] a diferencia del modelo REP (donde este diagnóstico se
# descartaba explícitamente por ser 2022 no comparable), aquí SÍ es un
# candidato legítimo para informar TURNOUT_CV -- ambos años son
# comparables. Se calcula y se muestra, pero se sigue usando el mismo
# valor manual (0.12) que el modelo REP por consistencia arquitectónica;
# queda como criterio explícito para que el usuario decida si prefiere
# usarlo en una siguiente iteración.
weighted_mean_diff_dem = np.average(county_master_dem['Diff_2022_vs_2018'], weights=county_master_dem['Reg_Dem'])
weighted_var_diff_dem = np.average(
    (county_master_dem['Diff_2022_vs_2018'] - weighted_mean_diff_dem) ** 2,
    weights=county_master_dem['Reg_Dem']
)
turnout_swing_std_pts_dem = np.sqrt(weighted_var_diff_dem)
print(f"[Diagnóstico] std ponderado del swing 2022 vs 2018 (Reg_Dem): {turnout_swing_std_pts_dem:.2f} pts. "
      f"A diferencia del modelo REP, aquí 2022 SÍ es válido -- este número podría legítimamente informar "
      f"TURNOUT_CV_ASSUMED_DEM en una futura iteración; se mantiene 0.12 (mismo valor que REP) por ahora, "
      f"por consistencia arquitectónica entre ambos modelos, no porque este diagnóstico se descarte.")

TURNOUT_CV_ASSUMED_DEM = 0.12  # mismo hiperparámetro asumido que el modelo REP, ver nota arriba
ensemble_estimates_dem = final_ensemble_estimates_dem

# FIX v9 (corrección post-elección 2026, aplicando al modelo DEM la misma
# corrección ya hecha en el modelo REP -- ver FIX v8 de pipeline_republican.py
# y docs/RESULTADOS_2026_VS_PRONOSTICO.md): 'early_vote_point_shares_dem' y
# 'undecided_allocation_point_dem' YA NO son el caso base del Monte Carlo
# (ver run_monte_carlo_dem) -- se conservan solo para que las filas de
# sensibilidad que explícitamente quieren un escenario de PUNTO FIJO
# (comparación contra el mecanismo viejo) sigan funcionando igual que antes.
# FIX v8: Joseph se agrega -- ver DECISIÓN METODOLÓGICA v8, celda 1.
early_vote_point_shares_dem = {
    'Jolly': ensemble_estimates_dem['Jolly']['mean'],
    'Foster': ensemble_estimates_dem['Foster']['mean'],
    'Joseph': ensemble_estimates_dem['Joseph']['mean'],
}
# FIX v9: EARLY_VOTE_CONFIDENCE_DEM cambia de significado, igual que en REP
# (FIX v8 republicano). Antes anclaba "early vote" a un punto fijo
# pre-calculado (early_vote_point_shares_dem) con baja confianza (25) --
# ahora ancla "early vote" a la composición YA REALIZADA de 'remaining' en
# la MISMA simulación, y controla qué tan chica es la perturbación
# independiente permitida. Se usa el MISMO valor recalibrado que REP (300)
# por consistencia arquitectónica entre ambos modelos (misma derivación:
# std ≈ sqrt(p(1-p)/(confidence+1)) -- con confidence=300 el std resultante
# de esa perturbación es de ~2.5-3 pts, dependiendo de p) -- no se deriva un
# valor propio para DEM porque no hay más datos aquí que en REP para
# calibrarlo con precisión distinta; se marca explícitamente como pendiente
# de verificación en el dry-run.
EARLY_VOTE_CONFIDENCE_DEM = 300         # hiperparámetro asumido -- recalibrado v9 (antes: 25, otro significado)
UNDECIDED_ALLOCATION_CONFIDENCE_DEM = 20  # mismo hiperparámetro asumido que REP
undecided_allocation_point_dem = dict(undecided_allocation_dem)  # ESCENARIO DE COMPARACIÓN, ya no es el base (ver FIX v9 arriba)

remaining_votes_preview_dem = total_expected_turnout_dem - total_early_votes_dem
print(f"\nVotos Esperados DEM (Reg_Dem x Avg_Pct_Gov_Primaries, promedio 2018+2022): "
      f"{total_expected_turnout_dem:,.0f}")
print(f"Votos Emitidos (Early, dato real Statewide_Totals): {total_early_votes_dem:,.0f} "
      f"({total_early_votes_dem/total_expected_turnout_dem*100:.1f}%)")
print(f"Votos Pendientes (Día de Elección, estimado): {remaining_votes_preview_dem:,.0f} "
      f"({(1 - total_early_votes_dem/total_expected_turnout_dem)*100:.1f}%)\n")

_ev_raw_total_dem = sum(early_vote_point_shares_dem.values())

# FIX v2 (bug de composición #1 de la auditoría): 'ensemble_estimates_dem'
# ya incluye el indeciso asignado por candidato (ver celda 3), así que
# Jolly+Foster puede sumar más de 100%. El código anterior imprimía ese
# total crudo tal cual y dejaba que rng.dirichlet() lo renormalizara EN
# SILENCIO dentro de la simulación: lo mostrado en pantalla no coincidía
# con el centro realmente simulado. Aquí se normaliza explícitamente
# ANTES de imprimir y de simular, para que ambos coincidan.
if _ev_raw_total_dem > 1.0:
    early_vote_point_shares_dem = {c: v / _ev_raw_total_dem for c, v in early_vote_point_shares_dem.items()}
    early_vote_others_share_dem = 0.0
    print(f"\n[Normalización early vote] Suma cruda Jolly+Foster+Joseph: {_ev_raw_total_dem*100:.1f}% "
          f"(> 100% -- el indeciso ya está incorporado en cada punto estimado). Se renormaliza "
          f"explícitamente dividiendo cada candidato por la suma cruda; 'Other_Minor' recibe 0% de early vote.")
else:
    early_vote_others_share_dem = max(1.0 - _ev_raw_total_dem, 0.0)

print(f"Prior de Early Vote DEM (centrado en el ensemble general, ya normalizado a 100%): "
      f"Jolly {early_vote_point_shares_dem['Jolly']*100:.1f}%, "
      f"Foster {early_vote_point_shares_dem['Foster']*100:.1f}%, "
      f"Joseph {early_vote_point_shares_dem['Joseph']*100:.1f}%, "
      f"Otros {early_vote_others_share_dem*100:.1f}%")
_ev_full_check_dem = sum(early_vote_point_shares_dem.values()) + early_vote_others_share_dem
assert abs(_ev_full_check_dem - 1.0) < 1e-9, \
    f"El prior de early vote DEM no suma 100% ({_ev_full_check_dem*100:.4f}%) -- revisar normalización."


def run_monte_carlo_dem(early_confidence, undecided_confidence, turnout_cv_value, n_simulations=10_000, seed=42,
                         verbose=False, ensemble_posteriors_ov=None, other_avg_ov=None, other_std_ov=None,
                         undecided_avg_ov=None, undecided_std_ov=None, undecided_allocation_ov=None,
                         early_vote_point_shares_ov=None, early_vote_others_share_ov=None,
                         undecided_to_other_share=0.0):
    """
    Simulación Monte Carlo DEM. Arquitectura análoga a run_monte_carlo()
    del modelo REP (v7: árbol Dirichlet/Beta de varios niveles con kappa
    propia por nivel, en vez de una sola Dirichlet compartida). El árbol
    queda en 3 niveles:
      Nivel 0 (Beta moment-matched): Unallocated_Residual vs. Decided
      Nivel 1 (Beta moment-matched): Other_Minor          vs. Pool_Candidatos (dentro de Decided)
      Nivel 2 (Dirichlet):           Jolly/Foster/Joseph                     (dentro de Pool)

    FIX v8 (individualización de Joseph, ver DECISIÓN METODOLÓGICA v8 en
    celda 1): el Nivel 2 vuelve a ser una Dirichlet de 3 categorías -- lo
    que era el diseño de v1-v4 (entonces Jolly/Foster/Demings), simplificado
    a Beta de 2 en v5 al retirar a Demings sin reemplazo. Se usa la MISMA
    convención que el modelo REP para su propio Nivel 2 de 3 categorías
    (Donalds/Collins/Fishback): un kappa "de compromiso" -- la MEDIANA de
    los 3 kappas implícitos por candidato -- porque una Dirichlet estándar
    solo tiene un grado de libertad de concentración total, no uno por
    categoría. A diferencia de Donalds/Collins/Fishback (kappas homogéneos,
    ~1.6x de spread), aquí el spread será MUCHO mayor: el kappa implícito de
    Joseph está dominado por JOSEPH_MIN_POLL_STD (celda 2, deliberadamente
    ancho, n=1) frente a los de Jolly/Foster (n=7, mucho más ajustados) --
    la mediana de 3 con un outlier tan marcado sigue siendo una elección
    defendible (no la arrastra tanto como un promedio), pero se documenta
    explícitamente como limitación, no se pretende que sea homogénea.

    FIX v9 (corrección post-elección 2026, aplicando al modelo DEM el mismo
    diagnóstico que el modelo REP -- ver docs/RESULTADOS_2026_VS_PRONOSTICO.md):
    el modelo REP repartía indecisos con un punto fijo elegido a mano
    (60/25/15) y sobreestimó al puntero en -10.4 pts. El modelo DEM NO
    elegía el reparto a mano (era proporcional al posterior de
    Jolly:Foster:Joseph, 78/11/10 aprox.) pero el efecto fue el mismo:
    sobreestimó a Jolly en -13.2 pts, con el mismo patrón (puntero
    sobreestimado, resto subestimado) que REP -- un ÚNICO vector fijo
    aplicado igual en las 10,000 simulaciones no deja lugar para que el
    residual se incline distinto de lo que el modelo ya asumía, sea cual
    sea el criterio (a mano o proporcional). Además, 'Other_Minor' fue la
    categoría peor calibrada de las dos carreras (mediana 4.8% vs. real
    14.3%, ver RESULTADOS_2026_VS_PRONOSTICO.md) y estaba excluida por
    diseño de recibir indecisos salvo por el parámetro bolt-on
    'undecided_to_other_share' (0.0 por defecto). Se corrige con la MISMA
    mezcla de 3 escenarios que REP, extendida a las 4 categorías
    [Jolly, Foster, Joseph, Other_Minor] -- ver bloque "Reparto de
    indecisos" más abajo. El punto fijo proporcional histórico
    ('undecided_allocation_point_dem') y el parámetro 'undecided_to_other_share'
    siguen disponibles para escenarios de comparación explícitos (ver
    'undecided_allocation_ov' y la nota en el bloque de reparto).
    """
    rng = np.random.default_rng(seed)

    ens_post = ensemble_posteriors_ov if ensemble_posteriors_ov is not None else ensemble_posteriors_dem
    o_avg = other_avg_ov if other_avg_ov is not None else other_minor_avg
    o_std = other_std_ov if other_std_ov is not None else other_minor_std
    u_avg = undecided_avg_ov if undecided_avg_ov is not None else current_unallocated_avg
    u_std = undecided_std_ov if undecided_std_ov is not None else unallocated_std
    # FIX v9: u_alloc/ev_shares YA NO caen de vuelta a un vector fijo global
    # cuando no se pasa override -- ver docstring arriba. Si no se pasa
    # override (u_alloc_ov/ev_shares_ov quedan en None), el reparto se
    # resuelve más abajo con la mezcla de escenarios nueva. Si SÍ se pasa un
    # override explícito, se preserva el comportamiento ANTERIOR exacto
    # (punto fijo) para que los escenarios de comparación sigan funcionando
    # igual que antes.
    u_alloc_ov = undecided_allocation_ov
    ev_shares_ov = early_vote_point_shares_ov
    ev_others_ov = early_vote_others_share_ov

    POOL_CANDS = ['Jolly', 'Foster', 'Joseph']

    pool_mean = sum(ens_post[c]['mean'] for c in POOL_CANDS)
    pool_var = sum(ens_post[c]['std'] ** 2 for c in POOL_CANDS)
    pool_std = np.sqrt(pool_var)

    # --- Nivel 0: Unallocated_Residual vs. Decided ---
    kappa_ud = max(u_avg * (1 - u_avg) / (u_std ** 2) - 1, 1.0)
    alpha_ud, beta_ud = u_avg * kappa_ud, (1 - u_avg) * kappa_ud
    S_undecided = rng.beta(alpha_ud, beta_ud, size=n_simulations)
    S_decided = 1.0 - S_undecided

    # --- Nivel 1: Other_Minor vs. Pool_Candidatos (dentro de Decided) ---
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

    # --- Nivel 2: reparto DENTRO del pool (Jolly/Foster/Joseph) -- Dirichlet ---
    within_means_raw = np.array([ens_post[c]['mean'] for c in POOL_CANDS]) / pool_mean
    within_stds_raw = np.array([ens_post[c]['std'] for c in POOL_CANDS]) / pool_mean
    within_kappas = (within_means_raw * (1 - within_means_raw)) / (within_stds_raw ** 2) - 1
    # FIX v9 (misma corrección que REP FIX v8): techo al kappa moment-matched
    # -- kappa moment-matched mide SOLO el desacuerdo observado entre
    # encuestas, que sistemáticamente SUBESTIMA la incertidumbre real cuando
    # las encuestas de una misma elección están correlacionadas ("herding").
    # Aquí el efecto es mucho menor que en REP en la práctica (el spread de
    # within_kappas ya está dominado por JOSEPH_MIN_POLL_STD, ver docstring),
    # pero se aplica el MISMO techo por consistencia arquitectónica y como
    # salvaguarda si Jolly/Foster llegan a tener kappas altos con más
    # encuestas en el futuro. NO calibrado contra datos (ver
    # docs/BACKTEST_RESULTS.md) -- misma advertencia que en REP.
    KAPPA_WITHIN_CAP = 30.0
    kappa_within = min(max(np.median(within_kappas), 1.0), KAPPA_WITHIN_CAP)
    within_alphas = np.clip(within_means_raw * kappa_within, 1e-3, None)
    simulated_within = rng.dirichlet(within_alphas, size=n_simulations)

    remaining_jolly_base = S_pool * simulated_within[:, 0]
    remaining_foster_base = S_pool * simulated_within[:, 1]
    remaining_joseph_base = S_pool * simulated_within[:, 2]

    # --- Reparto de indecisos ---
    # FIX v9 (corrección post-elección 2026, misma corrección que REP FIX
    # v8 -- ver docstring de esta función): reemplaza el punto fijo (a mano
    # en REP, proporcional-al-posterior aquí) por una MEZCLA de 3 escenarios
    # sorteada POR SIMULACIÓN sobre las 4 categorías [Jolly, Foster, Joseph,
    # Other_Minor] -- Other_Minor pasa a poder recibir residual de forma
    # orgánica dentro de la mezcla, así que el parámetro bolt-on
    # 'undecided_to_other_share' queda SIN EFECTO en este camino (se sigue
    # aceptando como argumento por compatibilidad, pero solo se usa en el
    # camino de comparación de punto fijo, rama 'else' de abajo):
    #   (a) Proporcional (peso 0.40): igual que el bloque YA decidido de esa
    #       simulación (mismo criterio validado en el backtest 2018-2022,
    #       MAE 2.04 pts, ver docs/BACKTEST_RESULTS.md).
    #   (b) Fragmentado (peso 0.35): reparto uniforme (1/4 cada uno).
    #   (c) Consolidación hacia el líder (peso 0.25): composición YA
    #       decidida elevada a un exponente > 1 (no un punto fijo elegido a
    #       mano ni derivado del posterior).
    # El punto fijo proporcional histórico ('undecided_allocation_dem')
    # sigue disponible como escenario de comparación explícito (ver celda de
    # sensibilidad, grupo 'indecisos') -- en ESE modo (u_alloc_ov no-None) se
    # preserva el comportamiento viejo EXACTO (Other_Minor excluido salvo por
    # 'undecided_to_other_share'), para que esas filas de comparación sigan
    # midiendo lo mismo que antes.
    if u_alloc_ov is None:
        GAMMA_CONSOLIDACION = 2.0
        SCENARIO_WEIGHTS_INDECISOS = np.array([0.40, 0.35, 0.25])
        decided_composition = np.stack(
            [remaining_jolly_base, remaining_foster_base, remaining_joseph_base, S_other], axis=1
        )
        decided_composition = decided_composition / decided_composition.sum(axis=1, keepdims=True)
        scenario_draw = rng.choice(3, size=n_simulations, p=SCENARIO_WEIGHTS_INDECISOS)
        alloc_proporcional = decided_composition
        alloc_fragmentado = np.full_like(decided_composition, 1.0 / decided_composition.shape[1])
        _powered = decided_composition ** GAMMA_CONSOLIDACION
        alloc_consolidacion = _powered / _powered.sum(axis=1, keepdims=True)
        _stack_alloc = np.stack([alloc_proporcional, alloc_fragmentado, alloc_consolidacion], axis=0)
        target_alloc_indecisos = _stack_alloc[scenario_draw, np.arange(n_simulations), :]
        alpha_matrix_indecisos = np.clip(target_alloc_indecisos * undecided_confidence, 1e-3, None)
        _g_ind = rng.gamma(alpha_matrix_indecisos)
        simulated_undecided_alloc = _g_ind / _g_ind.sum(axis=1, keepdims=True)
        if verbose:
            _sc_names = ['proporcional', 'fragmentado', 'consolidación_líder']
            _sc_counts = np.bincount(scenario_draw, minlength=3)
            print("Reparto de indecisos: MEZCLA de escenarios por simulación sobre 4 categorías "
                  "(Jolly/Foster/Joseph/Other_Minor, FIX v9) -- " +
                  ", ".join(f"{n}={c/n_simulations*100:.0f}%" for n, c in zip(_sc_names, _sc_counts)))
        remaining_jolly = remaining_jolly_base + S_undecided * simulated_undecided_alloc[:, 0]
        remaining_foster = remaining_foster_base + S_undecided * simulated_undecided_alloc[:, 1]
        remaining_joseph = remaining_joseph_base + S_undecided * simulated_undecided_alloc[:, 2]
        remaining_other = S_other + S_undecided * simulated_undecided_alloc[:, 3]
    else:
        S_undecided_to_other = S_undecided * undecided_to_other_share
        S_undecided_to_pool = S_undecided * (1.0 - undecided_to_other_share)
        undecided_alloc_alpha = [max(u_alloc_ov[c] * undecided_confidence, 1e-3) for c in POOL_CANDS]
        simulated_undecided_alloc = rng.dirichlet(undecided_alloc_alpha, size=n_simulations)
        remaining_jolly = remaining_jolly_base + S_undecided_to_pool * simulated_undecided_alloc[:, 0]
        remaining_foster = remaining_foster_base + S_undecided_to_pool * simulated_undecided_alloc[:, 1]
        remaining_joseph = remaining_joseph_base + S_undecided_to_pool * simulated_undecided_alloc[:, 2]
        remaining_other = S_other + S_undecided_to_other  # comportamiento viejo (comparación)

    # --- Early vote ---
    # FIX v9 (corrección post-elección 2026, misma corrección que REP FIX
    # v8): antes, "early vote" simulaba su PROPIA Dirichlet anclada a un
    # punto fijo pre-calculado (ev_shares) que YA incluía la asignación
    # puntual (sesgada) de indecisos. Ahora "early vote" se ancla a la
    # composición YA REALIZADA de 'remaining' en ESA MISMA simulación (que
    # ya incorpora la mezcla de escenarios de arriba, sin sesgo estructural)
    # y solo se le permite una perturbación INDEPENDIENTE modesta alrededor
    # de ese ancla -- el "ajuste de segundo orden" que debería ser.
    if ev_shares_ov is None:
        remaining_composition = np.stack(
            [remaining_jolly, remaining_foster, remaining_joseph, remaining_other], axis=1
        )
        # normalización de seguridad (deberían sumar 1.0 exacto por construcción)
        remaining_composition = remaining_composition / remaining_composition.sum(axis=1, keepdims=True)
        alpha_matrix_early = np.clip(remaining_composition * early_confidence, 1e-3, None)
        _g_early = rng.gamma(alpha_matrix_early)
        simulated_early_shares = _g_early / _g_early.sum(axis=1, keepdims=True)
    else:
        early_alpha = [ev_shares_ov[c] * early_confidence for c in POOL_CANDS]
        _ev_others = ev_others_ov if ev_others_ov is not None else early_vote_others_share_dem
        early_alpha.append(_ev_others * early_confidence)
        early_alpha = [max(a, 1e-3) for a in early_alpha]
        simulated_early_shares = rng.dirichlet(early_alpha, size=n_simulations)

    # --- Turnout (su propia incertidumbre) ---
    simulated_turnout = rng.normal(total_expected_turnout_dem, total_expected_turnout_dem * turnout_cv_value,
                                    size=n_simulations)
    simulated_turnout = np.clip(simulated_turnout, total_early_votes_dem, None)
    simulated_pct_remaining = 1.0 - (total_early_votes_dem / simulated_turnout)
    simulated_p_early = 1.0 - simulated_pct_remaining

    sim = pd.DataFrame(index=range(n_simulations), columns=['Jolly', 'Foster', 'Joseph', 'Other_Minor'], dtype=float)
    sim['Jolly'] = (simulated_early_shares[:, 0] * simulated_p_early) + (remaining_jolly * simulated_pct_remaining)
    sim['Foster'] = (simulated_early_shares[:, 1] * simulated_p_early) + (remaining_foster * simulated_pct_remaining)
    sim['Joseph'] = (simulated_early_shares[:, 2] * simulated_p_early) + (remaining_joseph * simulated_pct_remaining)
    sim['Other_Minor'] = (simulated_early_shares[:, 3] * simulated_p_early) + (remaining_other * simulated_pct_remaining)

    winner_pool = ['Jolly', 'Foster', 'Joseph']  # Other_Minor NO compite (Castillo-Bach/Fernandez/Norman agregados); Demings excluida (ver celda 1)
    sim['Winner'] = sim[winner_pool].idxmax(axis=1)

    if verbose:
        print(f"\nkappa nivel 0 (Unallocated_Residual vs. Decided, Beta moment-matched): {kappa_ud:.1f}")
        print(f"kappa nivel 1 (Other_Minor vs. Pool_Candidatos dentro de Decided, Beta moment-matched): {kappa_od:.1f}")
        print(f"kappa nivel 2 (Jolly/Foster/Joseph dentro del pool, Dirichlet -- kappas implícitos "
              f"{[round(float(k), 1) for k in within_kappas]} -> mediana usada: {kappa_within:.1f})")

    return {'sim_results': sim, 'winner_pool': winner_pool, 'n_simulations': n_simulations}


def recompute_and_simulate_dem(half_life_value=None, prior_overrides=None, undecided_center=None,
                                early_vote_shift=None, other_avg_override=None, turnout_cv_override=None,
                                other_impute_value=None,
                                undecided_to_other_share=None,
                                n_simulations=10_000, seed=42,
                                poll_subset=None):
    """Análogo a recompute_and_simulate() del modelo REP (v7): re-corre
    ponderación + ensemble desde una copia de polls_dem bajo un half_life
    / priors / centro de indecisos / early vote / Other alternativos.
    NO incluye una opción de house_effects on/off porque house_effects_dem
    está vacío por diseño (ver celda de ponderación) -- no hay nada
    significativo que alternar.

    FIX v6 (auditoría v5, punto 10 -- validación 'Modelo A vs. Modelo B'):
    nuevo parámetro opcional 'poll_subset' -- si se da, la función corre
    el pipeline completo (residuo -> promedio ponderado -> Bayes -> árbol
    -> early vote) sobre ESE subconjunto de encuestas en vez de las 7
    completas ('polls_dem_pre_impute'). Se usa en la celda 6 para correr
    un 'Modelo B' restringido solo a las 2 encuestas posteriores al retiro
    de Demings, como validación estructural independiente del 'Modelo A'
    (las 7 encuestas, con la corrección Retired_Mass/renormalización de
    arriba).

    FIX v3 (corrección del hallazgo más importante de la auditoría v2):
    se parte de 'polls_dem_pre_impute' (candidatos con sus NaN originales
    intactos) en vez de 'polls_dem' (que ya trae Unallocated_Residual fijo,
    calculado UNA vez con la imputación BASE). Esto permite que
    'other_impute_value' reconstruya el residuo de indecisos DESDE CERO.

    FIX v4 (separación explícita imputación-para-residual vs. soporte
    latente, pedida en la auditoría v3): cuando hay override explícito,
    el valor de escenario AHORA también se inyecta en la columna real del
    candidato (no solo en el cálculo del residuo) -- entra tanto al
    residuo como al promedio ponderado que alimenta al Nivel 1 del árbol
    (Other). Sin override, el comportamiento BASE es idéntico: NaN se
    queda como NaN en df[cand], fuera del promedio vía dropna().

    FIX v5 (consecuencia directa del retiro de Demings de winner_pool,
    ver nota crítica en celda 1): se elimina el parámetro
    'demings_impute_value' -- ya no existe ningún escenario de "¿y si
    Demings tuviera X% de soporte?" porque no compite. La columna
    'Demings' NUNCA entra a Bayes ni al árbol de composición. Solo
    'Other' conserva su mecanismo de imputación de escenario (missingness
    genuino de roster incompleto, no un retiro de candidatura).

    FIX v6 (corrección crítica #1 de la auditoría v5 -- 'Retired_Mass'
    NO debe convertirse en indeciso): réplica exacta, dentro de esta
    función, de la lógica de la celda 1 -- Retired_Mass (el valor
    histórico de Demings) se resta explícitamente del residuo (no se
    cuenta como indeciso) y Jolly/Foster/Other se renormalizan a
    J*=J/(J+F+O) SOLO en la única fila con tripleta completa + Demings
    reportada, para que la corrección llegue también al promedio
    ponderado y no solo al residuo. Ver comentarios detallados en celda 1."""
    hl = half_life_value if half_life_value is not None else half_life
    decay = np.log(2) / hl
    df = (poll_subset if poll_subset is not None else polls_dem_pre_impute).copy()

    df['Retired_Mass'] = df['Demings']

    # FIX v3: reconstrucción del residuo de indecisos bajo la imputación
    # de escenario, restringida a DEM_MODEL_COLS (Jolly/Foster/Other).
    #
    # FIX v4 (corrección del hallazgo principal de la auditoría v3): un
    # override como 'other_impute_value=0.15' ahora también se inyecta en
    # la columna real del candidato (df[cand]) -- entra tanto al residuo
    # como al promedio ponderado que alimenta al Nivel 1 del árbol
    # (Other), convirtiendo el escenario en un "full latent-support
    # stress" real. SIN override (BASE), df[cand] NO se toca -- las filas
    # sin ese candidato siguen siendo NaN y quedan fuera del promedio
    # ponderado vía dropna(), exactamente como antes; no se inyecta
    # ningún supuesto como si fuera dato medido.
    #
    # FIX v6: Retired_Mass se resta explícitamente (fillna(0) -- 0% por
    # definición en encuestas post-retiro, no "dato faltante").
    # FIX v8: JOSEPH_MIN_POLL_STD/pool ahora incluye a Joseph -- ver
    # comentario en la Prioridad "FIX v8" de la celda 1 para el mismo
    # tratamiento de other_impute_value -> 'Other_Minor' (ya no 'Other').
    _impute_overrides_pct = {}
    if other_impute_value is not None:
        _impute_overrides_pct['Other_Minor'] = other_impute_value * 100.0
    _impute_means = {
        c: (_impute_overrides_pct[c] if c in _impute_overrides_pct else df[c].mean())
        for c in DEM_MODEL_COLS
    }
    _imputed_for_resid = pd.DataFrame({c: df[c].fillna(_impute_means[c]) for c in DEM_MODEL_COLS})
    # FIX v8 (réplica exacta de la celda 1): Joseph no existía como
    # candidata calificada antes de JOSEPH_QUALIFICATION_DATE -- su
    # ausencia en esas filas es estructural (0%), no missingness genuino
    # de roster incompleto. Se sobrescribe con 0 en vez del promedio
    # general imputado.
    _joseph_pre_qualification = df['End_Date'] <= JOSEPH_QUALIFICATION_DATE
    _imputed_for_resid.loc[_joseph_pre_qualification, 'Joseph'] = 0.0
    df['Unallocated_Residual'] = (
        100 - _imputed_for_resid.sum(axis=1) - df['Retired_Mass'].fillna(0.0)
    ).clip(lower=0)

    # FIX v4: propagar el override también a la columna real (soporte
    # latente completo), no solo al cálculo del residuo.
    for c, v in _impute_overrides_pct.items():
        df[c] = df[c].fillna(v)

    # FIX v6: renormalización 'sobreviviente' -- idéntica a la celda 1.
    # FIX v8: 'Joseph' se agrega al loop de ModelInput (passthrough puro,
    # NO al denominador -- ver comentario idéntico en celda 1).
    _complete_triple = df[['Jolly', 'Foster', 'Other_Minor']].notna().all(axis=1)
    _has_retired_mass = df['Retired_Mass'].notna()
    _renorm_mask = _complete_triple & _has_retired_mass
    _survivor_denom = df['Jolly'] + df['Foster'] + df['Other_Minor']
    for _c in ['Jolly', 'Foster', 'Joseph', 'Other_Minor']:
        df[f'{_c}_ModelInput'] = np.where(
            _renorm_mask, df[_c] / _survivor_denom * 100.0, df[_c]
        )

    # FIX v7 (Prioridad 3, idéntico a la celda 1): no mezclar la escala
    # 'solo sobrevivientes' de las filas renormalizadas con la escala cruda
    # del residuo -- se anula su Unallocated_Residual para que
    # weighted_average() las excluya del nivel de indeciso sin dejar de
    # aportar posición relativa vía *_ModelInput.
    df.loc[_renorm_mask, 'Unallocated_Residual'] = np.nan

    for cand in ['Jolly', 'Foster', 'Joseph']:  # FIX v8: Joseph individualizada
        df[f'{cand}_Adj'] = df.apply(
            lambda r, cand=cand: apply_house_effects(r, cand, house_effects_dem, value_col=f'{cand}_ModelInput'),
            axis=1
        )

    df['Poll_Weight'] = df['Sample'] * np.exp(-decay * df['Days_Since_Poll'])

    pol_avg, pol_std = {}, {}
    for cand in ['Jolly', 'Foster', 'Joseph']:
        m = weighted_average(df, f'{cand}_Adj', 'Poll_Weight')
        s = poll_dispersion(df, f'{cand}_Adj', 'Poll_Weight', m)
        n_cand = df[cand].notna().sum()
        if cand == 'Joseph' and n_cand <= 1:
            s = max(s, JOSEPH_MIN_POLL_STD)  # FIX v8: mismo piso que la celda 2
        pol_avg[cand] = m / 100.0
        pol_std[cand] = s / 100.0

    o_avg = weighted_average(df, 'Other_Minor_ModelInput', 'Poll_Weight') / 100.0
    o_std = poll_dispersion(df, 'Other_Minor_ModelInput', 'Poll_Weight', o_avg * 100) / 100.0
    if other_avg_override is not None:
        o_avg = other_avg_override

    u_avg = weighted_average(df, 'Unallocated_Residual', 'Poll_Weight') / 100.0
    u_std = poll_dispersion(df, 'Unallocated_Residual', 'Poll_Weight', u_avg * 100) / 100.0

    priors_use = prior_overrides if prior_overrides is not None else subjective_priors_dem
    posteriors = {}
    for cand in priors_use.keys():
        pm, ps = priors_use[cand]['mean'], priors_use[cand]['std']
        dm, ds = pol_avg[cand], pol_std[cand]
        post_m, post_s = bayesian_update(pm, ps, dm, ds)
        posteriors[cand] = {'mean': post_m, 'std': post_s}

    # FIX v9 (corrección post-elección 2026, misma corrección que REP FIX
    # v8 -- ver recompute_and_simulate() de pipeline_republican.py): antes,
    # `alloc` SIEMPRE caía a un punto fijo (undecided_center si se pasó, si
    # no `undecided_allocation_dem`) y `ev_shares` SIEMPRE se derivaba de
    # ese punto fijo -- TODAS las filas de la celda de sensibilidad
    # (half_life, priors, early_vote, other_missingness, Modelo A/B, stress
    # test) heredaban el mecanismo viejo sin importar qué se estuviera
    # variando. Ahora: si el llamador NO pidió explícitamente un escenario
    # de punto fijo (undecided_center), un shift explícito de early vote
    # (early_vote_shift), ni un 'undecided_to_other_share' explícito, se
    # deja alloc_ov/ev_shares_ov/ev_others_ov en None para que
    # run_monte_carlo_dem use la MEZCLA de escenarios nueva -- igual que el
    # caso base. Nótese que 'other_avg_override' (solo) YA NO fuerza el
    # camino de punto fijo -- a diferencia de la versión anterior (que
    # necesitaba un bloque de coherencia manual para propagar Other al
    # early vote), la mezcla nueva + el anclaje de early vote a 'remaining'
    # (ver run_monte_carlo_dem) ya propagan o_avg de forma orgánica a
    # TODO el árbol (S_other entra a 'decided_composition' de la mezcla y a
    # 'remaining_composition' del early vote), así que ya no hace falta ese
    # bloque de coherencia -- se retira, no se preserva como rama muerta.
    if undecided_center is None and not early_vote_shift and undecided_to_other_share is None:
        alloc_ov, ev_shares_ov, ev_others_ov, uos_use = None, None, None, 0.0
    else:
        alloc = undecided_center if undecided_center is not None else undecided_allocation_dem
        final_est = {c: posteriors[c]['mean'] + u_avg * alloc[c] for c in posteriors}
        ev_shares = {c: final_est[c] for c in ['Jolly', 'Foster', 'Joseph']}  # FIX v8
        if early_vote_shift:
            for cand, delta in early_vote_shift.items():
                ev_shares[cand] = max(ev_shares[cand] + delta, 0.0)

        # FIX v2 (bug de composición #1) + FIX v2 (bug de composición #4:
        # coherencia con other_avg_override) -- preservado EXACTO para el
        # camino de comparación de punto fijo (rama 'else'): si hay override
        # de Other, se usa directamente como su share de early vote y J/F/Jo
        # se renormalizan para dejarle exactamente (1 - other_share) al
        # pool; si no hay override, se aplica la misma normalización
        # explícita que en el bloque principal de la celda 4.
        _ev_raw_total = sum(ev_shares.values())
        if other_avg_override is not None:
            ev_others = other_avg_override
            _target_jfd_total = max(1.0 - ev_others, 0.0)
            if _ev_raw_total > 0:
                ev_shares = {c: v / _ev_raw_total * _target_jfd_total for c, v in ev_shares.items()}
        elif _ev_raw_total > 1.0:
            ev_shares = {c: v / _ev_raw_total for c, v in ev_shares.items()}
            ev_others = 0.0
        else:
            ev_others = max(1.0 - _ev_raw_total, 0.0)
        alloc_ov, ev_shares_ov, ev_others_ov = alloc, ev_shares, ev_others
        uos_use = undecided_to_other_share if undecided_to_other_share is not None else 0.0

    turnout_cv_use = turnout_cv_override if turnout_cv_override is not None else TURNOUT_CV_ASSUMED_DEM

    _mc_result = run_monte_carlo_dem(
        EARLY_VOTE_CONFIDENCE_DEM, UNDECIDED_ALLOCATION_CONFIDENCE_DEM, turnout_cv_use,
        n_simulations=n_simulations, seed=seed,
        ensemble_posteriors_ov=posteriors, other_avg_ov=o_avg, other_std_ov=o_std,
        undecided_avg_ov=u_avg, undecided_std_ov=u_std, undecided_allocation_ov=alloc_ov,
        early_vote_point_shares_ov=ev_shares_ov, early_vote_others_share_ov=ev_others_ov,
        undecided_to_other_share=uos_use,
    )
    # FIX v7 (Prioridad 4 de la auditoría v6, 🟡 Media-baja -- "recalcular
    # priors neutros dentro de Modelo B"): se expone el promedio de
    # encuestas PROPIO de este subconjunto (pol_avg/pol_std, calculado
    # arriba a partir de 'df' = poll_subset si se pasó uno) además de lo
    # que ya devolvía run_monte_carlo_dem. Esto permite construir, fuera de
    # esta función, un prior neutro AUTOCONTENIDO para un subconjunto
    # (p. ej. Modelo B = solo post-retiro) sin depender de
    # 'subjective_priors_dem' (que se deriva del polling GLOBAL de Modelo
    # A) salvo que el llamador decida reutilizarlo a propósito.
    _mc_result['own_polling_avg'] = pol_avg
    _mc_result['own_polling_std'] = pol_std
    return _mc_result


def format_win_prob(n_wins, n_total):
    """Idéntica al modelo REP (v7) -- formato regla-de-tres."""
    upper_loss_bound = 3.0 / n_total * 100
    if n_wins == n_total:
        return f">{100 - upper_loss_bound:.2f}%"
    elif n_wins == 0:
        return f"<{upper_loss_bound:.2f}%"
    else:
        return f"{n_wins / n_total * 100:.2f}%"


def margin_stats_dem(sim, cand_a='Jolly', cand_b='Foster'):
    """FIX v3 (pedido explícitamente en la auditoría): el margen se
    calculaba como diferencia de medianas -- median(A) - median(B) --
    que NO es lo mismo que la mediana de la diferencia por simulación,
    median(A - B), salvo que la distribución conjunta sea simétrica.
    Aquí se calcula la diferencia DRAW-BY-DRAW (misma simulación, mismo
    sorteo de turnout/early vote/composición) y se reporta su mediana e
    IC95% -- estadísticamente consistente con los draws conjuntos, a
    diferencia de restar dos medianas marginales calculadas por separado."""
    diff = (sim[cand_a] - sim[cand_b]) * 100
    return {
        'median': np.median(diff),
        'lo95': np.percentile(diff, 2.5),
        'hi95': np.percentile(diff, 97.5),
    }


result_dem = run_monte_carlo_dem(EARLY_VOTE_CONFIDENCE_DEM, UNDECIDED_ALLOCATION_CONFIDENCE_DEM,
                                  TURNOUT_CV_ASSUMED_DEM, verbose=True)
sim_results_dem = result_dem['sim_results']
candidates_list_dem = result_dem['winner_pool']
winner_candidates_list_dem = candidates_list_dem + ['Other_Minor']
n_simulations_dem = result_dem['n_simulations']
win_probabilities_dem = sim_results_dem['Winner'].value_counts(normalize=True) * 100

print("-" * 40)
print("P(Jolly/Foster/Joseph gana | Castillo-Bach/Fernandez/Norman no pueden ganar individualmente) -- Tras 10,000 Simulaciones:")
print("NOTA v8 (individualización de Joseph, ver DECISIÓN METODOLÓGICA v8 en celda 1): winner_pool = "
      "['Jolly','Foster','Joseph'] -- 'Other_Minor' agrega a Castillo-Bach/Fernandez/Norman (sin datos "
      "propios para separarlos, ver celda 1) y NUNCA puede figurar como ganador de esa suma. La lista "
      "oficial de candidatos SÍ incluye a esos 3 individualmente, así que esto NO es una probabilidad "
      "electoral exhaustiva -- es la probabilidad CONDICIONAL de ganar entre Jolly/Foster/Joseph, bajo el "
      "supuesto estructural de que ninguno de Castillo-Bach/Fernandez/Norman gana individualmente. NOTA "
      "adicional: probabilidades CONDICIONALES a este modelo, NO calibradas electoralmente -- n=7 "
      "encuestas (n=1 para Joseph específicamente), sin Undecided real, sin house effects, priors "
      "neutros, reparto de indecisos derivado (no medido).")
for cand in candidates_list_dem:
    n_wins = int((sim_results_dem['Winner'] == cand).sum())
    display_prob = format_win_prob(n_wins, n_simulations_dem)
    extra = ""
    if n_wins == n_simulations_dem:
        extra = " (0 derrotas -> límite superior de pérdida ~3/n al 95% unilateral, regla de tres)"
    print(f" ► {cand}: {display_prob} ({n_wins:,}/{n_simulations_dem:,} simulaciones ganadas){extra}")
print("-" * 40)

print("\nRANGOS PROBABLES DE VOTO DEM (Intervalo del 95%):")
for cand in winner_candidates_list_dem:
    lower_bound = np.percentile(sim_results_dem[cand], 2.5) * 100
    upper_bound = np.percentile(sim_results_dem[cand], 97.5) * 100
    median_vote = np.median(sim_results_dem[cand]) * 100
    tag = "" if cand != 'Other_Minor' else "  (no compite por la victoria)"
    print(f" ► {cand}: Mediana {median_vote:.1f}%  (Rango: {lower_bound:.1f}% - {upper_bound:.1f}%){tag}")

row_sums_dem = sim_results_dem[winner_candidates_list_dem].sum(axis=1)
max_abs_dev_dem = np.max(np.abs(row_sums_dem - 1.0))
print(f"\n[Chequeo de consistencia] Suma fila a fila (por simulación) de todas las categorías: "
      f"min={row_sums_dem.min()*100:.4f}%, max={row_sums_dem.max()*100:.4f}%, "
      f"desviación máxima absoluta respecto a 100%: {max_abs_dev_dem*100:.6f} pts.")
assert max_abs_dev_dem < 1e-6, "Las simulaciones individuales no suman 1 -- hay una fuga o duplicación en la composición."


# =====================================================================
# CELDA "5. Salidas, Dashboards y Alertas (Demócrata)" -- NUEVA v1
# =====================================================================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

print("\nGenerando Salidas y Visualizaciones DEM...")

sns.set_theme(style="whitegrid")
# FIX v8: 'Joseph' se agrega con su propio color; 'Other' -> 'Other_Minor'.
colors_dem = {'Jolly': 'steelblue', 'Foster': 'darkorange', 'Joseph': 'mediumseagreen', 'Other_Minor': 'lightgray'}
# NOTA v5: 'Demings' ya no aparece aquí -- no compite, no se grafica su distribución simulada
# (nunca se simula, ver celda 4). Su serie histórica se documentó solo con fines de transparencia en
# la celda 2 (promedio ponderado pre-retiro).

plt.figure(figsize=(12, 6))
for cand in winner_candidates_list_dem:
    win_prob = (sim_results_dem['Winner'] == cand).mean() * 100 if cand in candidates_list_dem else 0.0
    label = f"{cand} (Win Prob: {win_prob:.1f}%)" if cand != 'Other_Minor' else f"{cand} (no compite)"
    sns.kdeplot(
        sim_results_dem[cand].astype(float) * 100,
        label=label, fill=True, alpha=0.4, color=colors_dem.get(cand, 'slategray'), linewidth=2
    )
plt.axvline(x=50, color='gray', linestyle='--',
            label='50% (referencia visual, NO es el umbral de victoria -- se gana por pluralidad)')
plt.title('Distribución Probable del Voto - Primaria Demócrata (Florida 2026)', fontsize=14, fontweight='bold')
plt.xlabel('Porcentaje de Votos Proyectado (%)', fontsize=12)
plt.ylabel('Densidad de Simulaciones', fontsize=12)
plt.legend(loc='upper right', frameon=True)
plt.tight_layout()
plt.savefig('election_forecast_density_dem.png', dpi=300)

print("\n--- ANÁLISIS DE SENSIBILIDAD DEM (TURNOUT) ---")
turnout_scenarios_dem = [0.9e6, 1.0e6, 1.07e6, 1.2e6, 1.4e6]
sensitivity_results_dem = []
sens_candidates_dem = ['Jolly', 'Foster', 'Joseph', 'Other_Minor']
sens_point_dem = {
    'Jolly': ensemble_estimates_dem['Jolly']['mean'],
    'Foster': ensemble_estimates_dem['Foster']['mean'],
    'Joseph': ensemble_estimates_dem['Joseph']['mean'],
    'Other_Minor': other_minor_avg,
}
_sens_total_raw_dem = sum(sens_point_dem.values())
print(f"\n[Normalización sens_point] Suma cruda antes de renormalizar: {_sens_total_raw_dem*100:.2f}% "
      f"(gap = {(_sens_total_raw_dem - 1.0)*100:+.2f} pts). Se renormaliza dividiendo cada categoría "
      f"por la suma cruda (misma técnica que el modelo REP).")
sens_point_dem = {k: v / _sens_total_raw_dem for k, v in sens_point_dem.items()}

early_point_full_dem = dict(early_vote_point_shares_dem)
early_point_full_dem['Other_Minor'] = early_vote_others_share_dem

# FIX v2 (bug de composición #2 de la auditoría): esta tabla combina
# 'early_point_full_dem' (early vote) con 'sens_point_dem' (remaining,
# YA renormalizado arriba) ponderados por su participación real en cada
# escenario de turnout. Antes, 'early_point_full_dem' se copiaba de
# 'early_vote_point_shares_dem' SIN renormalizar -- si esa suma cruda
# excedía 100% (como ocurría antes del fix de la celda 4), esta tabla
# heredaba el mismo sesgo (filas sumando 106.1%, 105.5%, ... en vez de
# 100%). Con la celda 4 ya corregida, 'early_point_full_dem' debería
# sumar exactamente 100% por construcción -- se verifica explícitamente
# aquí (assert) para que una futura regresión en la celda 4 no pase
# desapercibida en esta tabla, en vez de renormalizar en silencio.
_early_full_total_dem = sum(early_point_full_dem.values())
assert abs(_early_full_total_dem - 1.0) < 1e-6, (
    f"early_point_full_dem no suma 100% ({_early_full_total_dem*100:.4f}%) -- revisar la normalización "
    f"del early vote en la celda 4 (Simulación)."
)

for t in turnout_scenarios_dem:
    p_early_scn = total_early_votes_dem / t
    p_rem_scn = 1.0 - p_early_scn
    c_shares = []
    for cand in sens_candidates_dem:
        val = (early_point_full_dem[cand] * p_early_scn) + (sens_point_dem[cand] * p_rem_scn)
        c_shares.append(val)
    row_total = sum(c_shares)
    sensitivity_results_dem.append([f"{t/1e6:.2f}M"] + [f"{v*100:.1f}%" for v in c_shares] + [f"{row_total*100:.1f}%"])

sens_df_dem = pd.DataFrame(sensitivity_results_dem, columns=['Turnout Total (Millones)'] + sens_candidates_dem + ['Suma'])
print(sens_df_dem.to_string(index=False))
print("NOTA v6 (auditoría v5, punto 13): esta tabla sale PLANA (mismos % en todas las filas) NO por un bug, "
      "sino por identidad algebraica -- 'early_point_full_dem' (voto ya emitido) y 'sens_point_dem' "
      "(voto restante) están centrados en prácticamente la MISMA composición, así que "
      "p*E + (1-p)*E = E sin importar qué 'p' (fracción de early vote) resulte de cada escenario de turnout. "
      "Es decir: esta tabla hoy NO está probando sensibilidad real a la composición del electorado que aún "
      "no vota, solo re-confirma la misma composición bajo distintos denominadores de turnout total. No se "
      "corrige en esta versión (requeriría un supuesto explícito de que el remaining vote difiere del early "
      "vote, que no hay evidencia para fijar) -- se documenta para que no se lea como si fuera una prueba de "
      "sensibilidad de electorado, que no lo es.")

print("\n--- ALERTAS ELECTORALES DEM (bajo los supuestos de este modelo) ---")
alert_triggered_dem = False
jolly_margin = sim_results_dem['Jolly'].mean() - sim_results_dem['Foster'].mean()
if jolly_margin < 0.05:
    print("⚠️ ALERTA: La ventaja de Jolly ha caído a menos de 5 puntos.")
    alert_triggered_dem = True
win_prob_leader_dem = win_probabilities_dem.max()
if win_prob_leader_dem < 90:
    print(f"⚠️ ALERTA: La probabilidad de victoria del líder ({win_prob_leader_dem:.1f}%) bajó de 90%.")
    alert_triggered_dem = True
if not alert_triggered_dem:
    print("✅ Bajo los supuestos actuales del modelo, no se detecta una carrera cerrada.")

print("\n--- ALERTAS DE CALIDAD METODOLÓGICA DEM (siempre vigentes, no dependen del resultado) ---")
methodology_warnings_dem = []
methodology_warnings_dem.append(
    f"Solo {len(polls_dem)} encuestas Demócratas distintas tras deduplicar (vs. 39 del lado republicano) "
    f"-- un orden de magnitud menos de información; toda estimación es proporcionalmente más ruidosa."
)
methodology_warnings_dem.append(
    "NO existe columna 'Undecided' real -- se infirió como residuo por encuesta. FIX v2: el candidato "
    "ausente del roster de una encuesta se imputa con el promedio simple observado ANTES de calcular el "
    "residuo (en vez de tratar el residuo crudo como indeciso real), lo que reduce sustancialmente la "
    "sobreestimación -- pero sigue siendo una aproximación, no una medición. 'Unallocated_Residual_Naive' "
    "queda disponible para comparar. Ver aviso detallado en celda 1."
)
methodology_warnings_dem.append(
    "Con half_life=14 (mismo valor que REP, no recalibrado) y encuestas que van de 22 a 257 días de "
    "antigüedad, el promedio ponderado está dominado casi por completo por 1-2 encuestas recientes."
)
methodology_warnings_dem.append(
    "No se aplican house effects (a diferencia del modelo REP) -- no hay evidencia de sesgo específico "
    "por encuestadora para esta contienda; house_effects_dem queda vacío por diseño, no por omisión."
)
methodology_warnings_dem.append(
    "Los priors son NEUTROS (centrados en el propio promedio de encuestas, std=30pts) -- a diferencia del "
    "modelo REP, no hay fundamentales subjetivos declarados para Jolly/Foster en ningún archivo de esta "
    "carpeta. El Bayes no está aportando información adicional sobre el promedio de encuestas hoy."
)
methodology_warnings_dem.append(
    "FIX v9 (corrección post-elección 2026): el reparto de indecisos YA NO es un punto fijo (ni elegido a "
    "mano como en REP v7, ni proporcional al posterior como en este modelo hasta v8 -- ese punto fijo "
    "proporcional sobreestimó a Jolly en -13.2 pts en el resultado real) -- es una mezcla de 3 escenarios "
    "(proporcional 40%, fragmentado 35%, consolidación hacia el líder 25%) sorteada por simulación sobre "
    "4 categorías (Jolly/Foster/Joseph/Other_Minor). Sigue siendo un supuesto de diseño (los pesos "
    "0.40/0.35/0.25 no están calibrados con datos, ver docs/BACKTEST_RESULTS.md), no una medición -- misma "
    "corrección aplicada al modelo REP (ver methodology_warnings de pipeline_republican.py)."
)
methodology_warnings_dem.append(
    "FIX v9: la preferencia de candidato en el voto anticipado ya no se ancla a un punto fijo separado -- "
    "se ancla a la composición realizada de 'remaining' en la misma simulación, con una perturbación "
    "independiente modesta (EARLY_VOTE_CONFIDENCE_DEM, recalibrado a 300 -- ver celda 4, mismo valor y "
    "misma derivación que REP). Sigue siendo un supuesto (no se observa la preferencia real del voto "
    "anticipado), pero ya no puede fijar el pronóstico a un ancla potencialmente sesgada por sí solo."
)
methodology_warnings_dem.append(
    "CORRECCIÓN v5 (hallazgo crítico de la auditoría v4): Jerry Demings suspendió su candidatura el "
    "5-jun-2026 (diagnóstico de cáncer tratable, fuente: Florida Phoenix) y ya NO forma parte del roster "
    "oficial (Ballotpedia/Florida Phoenix/Local10: Jolly, Joseph, Foster, Castillo-Bach, Fernandez, "
    "Norman). Se excluyó de winner_pool y de todo cómputo de modelado (Bayes, árbol de composición) -- "
    "decisión del usuario (Opción 1). FIX v6 (corrección crítica de la auditoría v5): su soporte histórico "
    "medido ('Retired_Mass') ya NO cae dentro de Unallocated_Residual -- se resta explícitamente del "
    "residuo, y las encuestas pre-retiro con tripleta Jolly/Foster/Other_Minor completa se renormalizan a su "
    "posición relativa entre candidatos vigentes. Confirmado con datos propios: su missingness es un split "
    "temporal perfecto alineado con la fecha de retiro (ver celda 1), no un patrón de roster incompleto "
    "genérico."
)
methodology_warnings_dem.append(
    "CORRECCIÓN v6 (fecha corregida de la auditoría v5): Dotie Joseph quedó oficialmente calificada el "
    "12-jun-2026 (presentó papelería el 11-jun-2026) -- NO el 5-jul-2026 como afirmaba v5 (esa fecha es de "
    "cobertura mediática de su candidatura, no de su calificación oficial). Estaba calificada ANTES de las "
    "2 encuestas dominantes de julio. FIX v8: se individualiza como tercera candidata del pool "
    "(winner_pool=['Jolly','Foster','Joseph']) a partir de su única medición conocida (Change Research, "
    "6%) más la cobertura de AP que la nombra junto a Jolly y Foster entre los 6 demócratas calificados "
    "(ver DECISIÓN METODOLÓGICA v8, celda 1) -- pero su posterior está construido sobre UNA sola encuesta, "
    "con un piso de incertidumbre deliberadamente ancho (JOSEPH_MIN_POLL_STD=8pts) para no fingir precisión "
    "que no existe. Sigue sin poder verificarse si Other_Minor=8 de Change Research YA incluía su 6% -- ver "
    "'MAPEO JOSEPH: ESCENARIO A vs. ESCENARIO B' en la celda 6."
)
methodology_warnings_dem.append(
    "Turnout esperado usa Reg_Dem x Avg_Pct_Gov_Primaries (tasa general de TODOS los partidos, no "
    "específica de demócratas) -- misma limitación de fondo que el modelo REP, ver auditoría celda 1."
)
methodology_warnings_dem.append(
    "El CV de turnout (12%) es el MISMO hiperparámetro asumido que el modelo REP, no recalibrado con el "
    "diagnóstico de swing 2022-vs-2018 (que aquí SÍ sería válido, a diferencia de REP)."
)
methodology_warnings_dem.append(
    "El forecast no tiene backtesting contra elecciones pasadas -- P(win) es condicional al modelo, no "
    "una probabilidad electoral calibrada."
)
methodology_warnings_dem.append(
    "CORRECCIÓN v6 (auditoría v5, punto 9) + v7 (auditoría v6, punto 7): las tablas heredadas de v7 "
    "(tornado, sensibilidad estructural, Modelo A/B, stress test) usan 'P(Jolly > Foster)'/'P(Foster > "
    "Jolly)' en vez de 'P(Jolly gana)'/'P(Foster gana)', para no leerse como probabilidad electoral "
    "exhaustiva fuera de contexto. FIX v8: con Joseph individualizada, el P(win) PRIMARIO de esta celda ya "
    "es P(Jolly/Foster/Joseph gana), genuinamente más cercano a exhaustivo que en v7 -- solo excluye a "
    "Castillo-Bach/Fernandez/Norman (agregados en 'Other_Minor', sin datos propios para separarlos, ver "
    "celda 1). Las tablas heredadas de v7 (que comparan específicamente Jolly vs. Foster, p.ej. la "
    "sensibilidad de priors 'ADVERSO a Jolly') mantienen su fraseo 'X > Y' porque siguen midiendo "
    "exactamente eso -- un margen entre dos candidatos, no P(win) de 3."
)
for w in methodology_warnings_dem:
    print(f"⚠ {w}")


# =====================================================================
# CELDA "6. Sensibilidad de Hiperparámetros (Demócrata)" -- NUEVA v1
# =====================================================================
import numpy as np
import pandas as pd

print("Corriendo análisis de sensibilidad de hiperparámetros DEM (esto toma unos segundos)...\n")

BASE_EARLY_CONF_DEM = EARLY_VOTE_CONFIDENCE_DEM
BASE_UNDECIDED_CONF_DEM = UNDECIDED_ALLOCATION_CONFIDENCE_DEM
BASE_TURNOUT_CV_DEM = TURNOUT_CV_ASSUMED_DEM

# FIX v9: rango de EARLY_VOTE_CONFIDENCE_DEM recalibrado -- mismo motivo
# que REP FIX v8 (nuevo significado: perturbación alrededor de 'remaining',
# no ancla a un punto fijo separado); 100-600 cubre de "early vote puede
# diferir varios puntos de remaining" a "early vote casi idéntico a
# remaining".
scenario_grids_dem = {
    'EARLY_VOTE_CONFIDENCE': [100, 200, 300, 600],
    'UNDECIDED_ALLOCATION_CONFIDENCE': [5, 10, 20, 50],
    'TURNOUT_CV_ASSUMED': [0.05, 0.10, 0.15, 0.20],
}

tornado_rows_dem = []
for param_name, grid in scenario_grids_dem.items():
    for value in grid:
        kwargs = dict(early_confidence=BASE_EARLY_CONF_DEM,
                       undecided_confidence=BASE_UNDECIDED_CONF_DEM,
                       turnout_cv_value=BASE_TURNOUT_CV_DEM)
        if param_name == 'EARLY_VOTE_CONFIDENCE':
            kwargs['early_confidence'] = value
        elif param_name == 'UNDECIDED_ALLOCATION_CONFIDENCE':
            kwargs['undecided_confidence'] = value
        else:
            kwargs['turnout_cv_value'] = value

        r = run_monte_carlo_dem(**kwargs, n_simulations=10_000, seed=42)
        sim = r['sim_results']
        n_tot = r['n_simulations']
        n_jolly = int((sim['Winner'] == 'Jolly').sum())
        n_foster = int((sim['Winner'] == 'Foster').sum())
        mstats = margin_stats_dem(sim)
        median_margin = mstats['median']
        lo = np.percentile(sim['Jolly'], 2.5) * 100
        hi = np.percentile(sim['Jolly'], 97.5) * 100
        is_base = (
            (param_name == 'EARLY_VOTE_CONFIDENCE' and value == BASE_EARLY_CONF_DEM) or
            (param_name == 'UNDECIDED_ALLOCATION_CONFIDENCE' and value == BASE_UNDECIDED_CONF_DEM) or
            (param_name == 'TURNOUT_CV_ASSUMED' and value == BASE_TURNOUT_CV_DEM)
        )
        tornado_rows_dem.append({
            'Hiperparámetro': param_name, 'Valor': value, '(base)': 'sí' if is_base else '',
            'P(Jolly > Foster)': format_win_prob(n_jolly, n_tot),
            'P(Foster > Jolly)': format_win_prob(n_foster, n_tot),
            'Margen mediano J-F (pts)': round(median_margin, 1),
            'Margen IC95% (pts)': f"{mstats['lo95']:.1f} a {mstats['hi95']:.1f}",
            'Jolly IC95%': f"{lo:.1f}%-{hi:.1f}%",
            '_margin_raw': median_margin,
        })

tornado_df_dem = pd.DataFrame(tornado_rows_dem)
print(tornado_df_dem.drop(columns=['_margin_raw']).to_string(index=False))

print("\n--- LECTURA ---")
for param_name in scenario_grids_dem:
    sub = tornado_df_dem[tornado_df_dem['Hiperparámetro'] == param_name]
    spread = sub['_margin_raw'].max() - sub['_margin_raw'].min()
    print(f"{param_name}: margen mediano J-F varía {spread:.1f} pts entre los escenarios probados "
          f"({sub['_margin_raw'].min():.1f} - {sub['_margin_raw'].max():.1f} pts).")

max_spread_param_dem = max(scenario_grids_dem, key=lambda p: (
    tornado_df_dem[tornado_df_dem['Hiperparámetro'] == p]['_margin_raw'].max()
    - tornado_df_dem[tornado_df_dem['Hiperparámetro'] == p]['_margin_raw'].min()
))
print(f"\nEl hiperparámetro que más mueve el margen mediano J-F es: {max_spread_param_dem}.")

print("\n\nCorriendo sensibilidad ESTRUCTURAL DEM (half_life, priors, centro de indecisos, "
      "missingness de Other, escenarios adversos)...\n")

# v5: shifted_priors tenía solo 2 claves (Jolly/Foster) -- consecuencia
# directa de retirar a Demings del pool de modelado (ver celda 1). El
# desplazamiento adverso/favorable de Jolly se compensaba enteramente en
# Foster (antes se repartía entre Foster y Demings).
# FIX v8: con Joseph ahora en subjective_priors_dem (3 claves), un dict
# comprehension genérico sobre TODAS las claves desplazaría también su
# prior -- pero las etiquetas de este escenario dicen explícitamente
# "Foster -5pts"/"Foster +5pts", no "Foster Y Joseph". Se restringe el
# desplazamiento a Jolly/Foster EXPLÍCITAMENTE; el prior de Joseph queda
# sin tocar en este escenario (sigue centrado en su propio polling, con su
# std ancho de siempre) -- esta sensibilidad sigue midiendo específicamente
# el eje Jolly-vs-Foster, no un desplazamiento de 3 vías.
shifted_priors_favorable_dem = dict(subjective_priors_dem)
shifted_priors_favorable_dem['Jolly'] = {
    'mean': subjective_priors_dem['Jolly']['mean'] + 0.05, 'std': subjective_priors_dem['Jolly']['std']
}
shifted_priors_favorable_dem['Foster'] = {
    'mean': max(subjective_priors_dem['Foster']['mean'] - 0.05, 0.001), 'std': subjective_priors_dem['Foster']['std']
}
shifted_priors_adverse_dem = dict(subjective_priors_dem)
shifted_priors_adverse_dem['Jolly'] = {
    'mean': max(subjective_priors_dem['Jolly']['mean'] - 0.05, 0.001), 'std': subjective_priors_dem['Jolly']['std']
}
shifted_priors_adverse_dem['Foster'] = {
    'mean': subjective_priors_dem['Foster']['mean'] + 0.05, 'std': subjective_priors_dem['Foster']['std']
}
_j0, _f0, _jo0 = undecided_allocation_dem['Jolly'], undecided_allocation_dem['Foster'], undecided_allocation_dem['Joseph']

# FIX v8: undecided_allocation_dem ahora tiene 3 claves (Jolly/Foster/
# Joseph, ver celda 3). Los escenarios "Favorable/ADVERSO a Jolly" siguen
# siendo específicamente sobre el eje Jolly-vs-Foster (así lo dicen sus
# etiquetas) -- se mantiene la participación de Joseph en su valor BASE
# derivado (_jo0) y se reparte el remanente (1 - _jo0) entre Jolly/Foster
# según la proporción 95/5 o 55/45, en vez de simplemente omitir a Joseph
# del diccionario (lo que causaría un KeyError más abajo, porque
# ensemble_posteriors_dem/undecided_alloc_alpha ya esperan 3 claves).
_remainder_share_jf = 1.0 - _jo0
def _undecided_scenario_jf(jolly_frac, foster_frac):
    return {'Jolly': jolly_frac * _remainder_share_jf, 'Foster': foster_frac * _remainder_share_jf, 'Joseph': _jo0}

structural_scenarios_dem = [
    {'grupo': 'half_life', 'label': '7d (más peso a lo reciente)', 'kwargs': dict(half_life_value=7)},
    {'grupo': 'half_life', 'label': '14d (BASE)', 'kwargs': dict(half_life_value=14), 'is_base': True},
    {'grupo': 'half_life', 'label': '21d', 'kwargs': dict(half_life_value=21)},
    # FIX v6 (auditoría v5, punto 15 -- etiqueta textual incorrecta): a
    # 257 días de antigüedad (la encuesta más vieja), 2^(-257/30) ≈ 0.0026
    # -- sigue siendo un decaimiento enorme, no "casi sin decaimiento".
    # Se relabela como "decaimiento más lento" (correcto: MÁS lento que
    # 7/14/21d, no "ausente").
    {'grupo': 'half_life', 'label': '30d (decaimiento más lento)', 'kwargs': dict(half_life_value=30)},
    # FIX v9: el reparto proporcional-al-posterior de punto fijo YA NO es
    # el base (era exactamente el mecanismo que sobreestimó a Jolly -13.2
    # pts en el resultado real 2026, el mismo patrón que REP con su punto
    # fijo 60/25/15 -- ver docs/RESULTADOS_2026_VS_PRONOSTICO.md) -- se
    # conserva como escenario de comparación explícito. El nuevo base es la
    # mezcla de escenarios (kwargs=dict() activa el camino nuevo en
    # run_monte_carlo_dem, igual que el resto de grupos de esta tabla).
    {'grupo': 'indecisos', 'label': 'Mezcla de escenarios 40/35/25% (NUEVO BASE v9, ver FIX v9 celda 4)',
     'kwargs': dict(), 'is_base': True},
    {'grupo': 'indecisos', 'label': f'Proporcional J{_j0*100:.0f}/F{_f0*100:.0f}/Jo{_jo0*100:.0f} punto fijo '
                                     f'(MECANISMO VIEJO -- sobreestimó a Jolly -13.2 pts en 2026)',
     'kwargs': dict(undecided_center=undecided_allocation_dem)},
    # v5: escenarios de indecisos ahora 2-way (Jolly/Foster) -- Demings ya
    # no participa del reparto de indecisos (no compite).
    # FIX v7 (Prioridad 5 de la auditoría v6, 🟡 Baja -- etiqueta
    # incorrecta): el reparto BASE derivado del polling es {_j0*100:.0f}/
    # {_f0*100:.0f} (87/13 en la práctica) -- 85/15 es LIGERAMENTE MENOS
    # favorable a Jolly que el BASE (menos de 87, más de 13), no más
    # favorable como decía la etiqueta v5/v6 (el margen de hecho cae de
    # 71.3 a 69.4 pts con ese escenario). Se sube a 95/5 -- un valor
    # genuinamente más favorable que el BASE en ambas coordenadas -- y se
    # relabela en consecuencia.
    {'grupo': 'indecisos', 'label': 'Favorable a Jolly (95/5 del remanente J:F, Joseph en su valor BASE)',
     'kwargs': dict(undecided_center=_undecided_scenario_jf(0.95, 0.05))},
    {'grupo': 'indecisos', 'label': 'ADVERSO a Jolly (55/45 del remanente J:F, Joseph en su valor BASE)',
     'kwargs': dict(undecided_center=_undecided_scenario_jf(0.55, 0.45))},
    {'grupo': 'priors', 'label': 'Neutros (BASE)', 'kwargs': dict(prior_overrides=subjective_priors_dem), 'is_base': True},
    {'grupo': 'priors', 'label': 'Favorable a Jolly (+5pts, Foster -5pts)',
     'kwargs': dict(prior_overrides=shifted_priors_favorable_dem)},
    {'grupo': 'priors', 'label': 'ADVERSO a Jolly (-5pts, Foster +5pts)',
     'kwargs': dict(prior_overrides=shifted_priors_adverse_dem)},
    {'grupo': 'early_vote', 'label': 'Centrado en ensemble (BASE)', 'kwargs': dict(), 'is_base': True},
    {'grupo': 'early_vote', 'label': 'ADVERSO (Jolly -5pts, Foster +5pts)',
     'kwargs': dict(early_vote_shift={'Jolly': -0.05, 'Foster': 0.05})},
    # FIX v3 (pedido explícitamente): 'undecided_to_other_share' permite
    # que parte del residual (Unallocated_Residual, ver celda 1 -- ni
    # siquiera es indeciso puramente observado) termine en 'Other' en vez
    # de repartirse SIEMPRE 100% entre Jolly/Foster.
    #
    # FIX v6 (auditoría v5, puntos 5 y 6): el reparto BASE (undecided_
    # allocation_dem, celda 3) es proporcional SOLO a Jolly:Foster
    # (87.1/12.9) -- pese a describirse como "proporcional al polling
    # actual", en realidad excluye a Other de ese cálculo por
    # construcción (Other siempre recibe 0% del residual en el escenario
    # BASE de este grupo). Si se repartiera proporcionalmente a TODO el
    # polling activo (J:F:O), Other se llevaría ~9-10% del residual, no
    # 0%. Por eso 0% no es un punto neutro sino el extremo "Other=0" de
    # este rango -- y el escenario "10% del indeciso a Other" es, de
    # hecho, la aproximación más cercana a lo que sería un reparto
    # genuinamente proporcional a los 3 candidatos. Dado que
    # Unallocated_Residual es grande (~43%, ver celda 2) y su composición
    # real (indeciso genuino vs. candidatos menores no itemizados) es
    # desconocida, se amplía el rango de 0-10% a 0-50% -- no porque 50%
    # se considere probable, sino porque no hay evidencia para descartarlo
    # y el rango anterior (máx. ~4.3 pts de Unallocated_Residual) era
    # demasiado angosto para acotar honestamente esta incertidumbre.
    #
    # FIX v9: NINGUNA fila de este grupo es 'BASE' ya -- pasar
    # 'undecided_to_other_share' explícitamente (incluido 0.0) activa la
    # rama de PUNTO FIJO en run_monte_carlo_dem (ver docstring), así que
    # las 4 filas de abajo miden el mecanismo VIEJO a distintos niveles de
    # fuga hacia Other_Minor -- no el modelo vigente. El modelo vigente
    # (mezcla de escenarios, grupo 'indecisos' arriba) ya deja que
    # Other_Minor reciba residual de forma orgánica, así que este grupo
    # queda como comparación histórica, no como sensibilidad del base.
    {'grupo': 'undecided_a_other (MECANISMO VIEJO)', 'label': '0% a Other_Minor (punto fijo, paridad con v8)',
     'kwargs': dict(undecided_to_other_share=0.0)},
    {'grupo': 'undecided_a_other (MECANISMO VIEJO)', 'label': '10% a Other_Minor (punto fijo)',
     'kwargs': dict(undecided_to_other_share=0.10)},
    {'grupo': 'undecided_a_other (MECANISMO VIEJO)', 'label': '25% a Other_Minor (punto fijo)',
     'kwargs': dict(undecided_to_other_share=0.25)},
    {'grupo': 'undecided_a_other (MECANISMO VIEJO)', 'label': '50% a Other_Minor (punto fijo, extremo)',
     'kwargs': dict(undecided_to_other_share=0.50)},
]

structural_rows_dem = []
for scn in structural_scenarios_dem:
    r = recompute_and_simulate_dem(**scn['kwargs'], n_simulations=10_000, seed=42)
    sim = r['sim_results']
    n_tot = r['n_simulations']
    n_jolly = int((sim['Winner'] == 'Jolly').sum())
    n_foster = int((sim['Winner'] == 'Foster').sum())
    mstats = margin_stats_dem(sim)
    lo = np.percentile(sim['Jolly'], 2.5) * 100
    hi = np.percentile(sim['Jolly'], 97.5) * 100
    structural_rows_dem.append({
        'Grupo': scn['grupo'], 'Escenario': scn['label'], '(base)': 'sí' if scn.get('is_base') else '',
        'P(Jolly > Foster)': format_win_prob(n_jolly, n_tot),
        'P(Foster > Jolly)': format_win_prob(n_foster, n_tot),
        'Margen mediano J-F (pts)': round(mstats['median'], 1),
        'Margen IC95% (pts)': f"{mstats['lo95']:.1f} a {mstats['hi95']:.1f}",
        'Jolly IC95%': f"{lo:.1f}%-{hi:.1f}%",
    })

# Sensibilidad de missingness: 'Other' se estima sobre un subconjunto
# parcial de las 7 encuestas (4/7) -- análogo al chequeo Other_Named del
# modelo REP. (v5: el chequeo equivalente para 'Demings' se ELIMINÓ por
# completo -- ya no es missingness de roster incompleto, es un candidato
# que se retiró; no existe ningún escenario legítimo de "¿y si tuviera
# X% de soporte?" para alguien que no compite. Ver nota crítica celda 1.)
#
# FIX v4 (bug de missingness señalado explícitamente en la auditoría v3):
# en v2/v3 este bloque llamaba a run_monte_carlo_dem(..., other_avg_ov=o_val),
# que sí cambiaba el peso de 'Other' en el árbol composicional PERO NO
# reconstruía Unallocated_Residual en las 3 encuestas donde 'Other' falta.
# Ahora se usa recompute_and_simulate_dem(other_avg_override=o_val,
# other_impute_value=o_val), que reconstruye el residuo Y ADEMÁS (FIX v4)
# inyecta o_val como soporte latente completo en las filas donde 'Other'
# falta -- 'other_avg_override' además garantiza que el share efectivo en
# el árbol sea EXACTAMENTE o_val incluso si esas 3 encuestas pesan poco.
other_scenarios_dem = [
    ('Other_Minor = polling crudo (BASE)', None, True),
    ('Other_Minor = 5% (extremo bajo, ilustrativo, soporte latente completo)', 0.05, False),
    ('Other_Minor = 15% (extremo alto, ilustrativo, soporte latente completo)', 0.15, False),
]
for label, o_val, is_base in other_scenarios_dem:
    r = recompute_and_simulate_dem(other_avg_override=o_val, other_impute_value=o_val,
                                    n_simulations=10_000, seed=42)
    sim = r['sim_results']
    n_tot = r['n_simulations']
    n_jolly = int((sim['Winner'] == 'Jolly').sum())
    n_foster = int((sim['Winner'] == 'Foster').sum())
    mstats = margin_stats_dem(sim)
    lo = np.percentile(sim['Jolly'], 2.5) * 100
    hi = np.percentile(sim['Jolly'], 97.5) * 100
    structural_rows_dem.append({
        'Grupo': 'other_missingness', 'Escenario': label, '(base)': 'sí' if is_base else '',
        'P(Jolly > Foster)': format_win_prob(n_jolly, n_tot),
        'P(Foster > Jolly)': format_win_prob(n_foster, n_tot),
        'Margen mediano J-F (pts)': round(mstats['median'], 1),
        'Margen IC95% (pts)': f"{mstats['lo95']:.1f} a {mstats['hi95']:.1f}",
        'Jolly IC95%': f"{lo:.1f}%-{hi:.1f}%",
    })

structural_df_dem = pd.DataFrame(structural_rows_dem)
print(structural_df_dem.to_string(index=False))

print("\n--- LECTURA (sensibilidad estructural DEM) ---")
print("half_life: dado el aviso crítico de la celda 2 (2 encuestas concentran casi todo el peso), se "
      "espera un efecto MAYOR aquí que en el modelo REP.")
print("Indecisos: FIX v9 -- el BASE ya NO es el punto fijo proporcional al polling; es la mezcla de 3 "
      "escenarios (proporcional/fragmentado/consolidación) sobre 4 categorías, la misma corrección "
      "aplicada al modelo REP tras el resultado real 2026 (ver docs/RESULTADOS_2026_VS_PRONOSTICO.md). "
      "El punto fijo derivado y los escenarios 95/5 y 55/45 quedan como comparación histórica.")
print("Priors: se prueban ambas direcciones, aunque el prior BASE ya es neutro (no jala hacia ningún lado).")
print("Undecided a Other (MECANISMO VIEJO): FIX v9 -- este grupo entero pasó a ser un escenario de punto "
      "fijo (ya no representa el BASE) porque cualquier 'undecided_to_other_share' explícito activa el "
      "camino de comparación de punto fijo en run_monte_carlo_dem. Bajo el BASE nuevo (mezcla de "
      "escenarios), Other_Minor ya recibe residual de forma orgánica sin necesitar este parámetro -- se "
      "conserva solo para comparar contra el mecanismo viejo a distintos niveles de fuga hacia Other_Minor.")
print("Other/missingness: 'Other' se estima sobre solo 4/7 encuestas -- el rango 5%-15% acota la "
      "incertidumbre de esa estimación.")
print("NOTA v5: el bloque de sensibilidad de missingness de 'Demings' (presente en v1-v4) se eliminó -- "
      "ya no es una candidata del modelo, ver corrección crítica en celda 1.")
print("NOTA v6: se añade más abajo una comparación estructural 'Modelo A (7 encuestas) vs. Modelo B "
      "(solo post-retiro)' como validación independiente -- ver auditoría v5, punto 10.")

print("\n\n" + "=" * 70)
print("VALIDACIÓN ESTRUCTURAL DEM -- MODELO A (7 encuestas) vs. MODELO B (solo post-retiro)")
print("=" * 70)
# FIX v6 (auditoría v5, punto 10 -- pedido explícitamente, no implementado
# en v5): 'Modelo A' es el modelo BASE de este notebook (las 7 encuestas,
# con Retired_Mass separado del residuo y renormalización 'sobreviviente'
# donde aplica). 'Modelo B' usa EXCLUSIVAMENTE las 2 encuestas posteriores
# al retiro de Demings (Targoz LV, Change Research) -- que ya concentran
# 99.7% del peso de Modelo A a half_life=14, así que se espera que ambos
# modelos coincidan de cerca; si no coincidieran, sería señal de que las 5
# encuestas antiguas SÍ están moviendo el resultado de forma no trivial
# pese a su peso marginal, y habría que revisar por qué.
# NO se propone Modelo B como el forecast principal -- es una validación
# de robustez, exactamente como se pidió.
_post_suspension_mask_b = polls_dem_pre_impute['End_Date'] > DEMINGS_SUSPENSION_DATE
polls_post_retiro_dem = polls_dem_pre_impute[_post_suspension_mask_b].copy()
print(f"Modelo B usa {len(polls_post_retiro_dem)} encuesta(s): "
      f"{', '.join(polls_post_retiro_dem['Poll_Source'].tolist())}")

r_modelo_a = recompute_and_simulate_dem(n_simulations=10_000, seed=42)  # = BASE, siete encuestas

# FIX v7 (Prioridad 4 de la auditoría v6, 🟡 Media-baja): antes, Modelo B
# reutilizaba 'subjective_priors_dem' -- un prior neutro derivado del
# promedio de encuestas de Modelo A (las 7 encuestas, incluida la
# renormalización 'sobreviviente' de Emerson). Eso mezclaba, dentro de la
# validación de robustez, información de Modelo A dentro de Modelo B --
# exactamente lo que la comparación A-vs-B pretende evitar. Para que
# Modelo B sea genuinamente independiente, se corre primero una llamada
# 'sonda' SOLO para obtener el promedio de encuestas propio de las 2
# encuestas post-retiro ('own_polling_avg'), y con ESE promedio (no el de
# Modelo A) se construye un prior neutro igual de ancho
# (NEUTRAL_PRIOR_STD=0.30) autocontenido para Modelo B.
_probe_b = recompute_and_simulate_dem(poll_subset=polls_post_retiro_dem, n_simulations=10_000, seed=42)
# FIX v8: 'Joseph' se agrega -- imprescindible (no solo por completitud):
# recompute_and_simulate_dem() y run_monte_carlo_dem() ahora ESPERAN un
# posterior para las 3 claves del pool ('POOL_CANDS'); un prior_overrides
# con solo Jolly/Foster produciría un KeyError al construir la Dirichlet
# del Nivel 2. Change Research (única fuente del dato de Joseph) es
# también la única de las 2 encuestas de Modelo B que la reporta, así que
# 'own_polling_avg' ya trae su valor propio (con el piso
# JOSEPH_MIN_POLL_STD aplicado igual que en Modelo A).
subjective_priors_b_dem = {
    cand: {'mean': _probe_b['own_polling_avg'][cand], 'std': NEUTRAL_PRIOR_STD}
    for cand in ['Jolly', 'Foster', 'Joseph']
}
print(f"\n[FIX v7 -- Modelo B autocontenido] Prior neutro propio de Modelo B (solo Targoz LV + Change "
      f"Research, NO derivado de las 7 encuestas de Modelo A): " +
      ", ".join(f"{c} {v['mean']*100:.1f}%" for c, v in subjective_priors_b_dem.items()) +
      f" (Modelo A usaba: " +
      ", ".join(f"{c} {subjective_priors_dem[c]['mean']*100:.1f}%" for c in subjective_priors_dem) + ")")
r_modelo_b = recompute_and_simulate_dem(poll_subset=polls_post_retiro_dem, prior_overrides=subjective_priors_b_dem,
                                         n_simulations=10_000, seed=42)

_modelo_rows = []
for _label, _r in [('Modelo A (7 encuestas)', r_modelo_a), ('Modelo B (solo post-retiro, n=2)', r_modelo_b)]:
    _sim = _r['sim_results']
    _n_tot = _r['n_simulations']
    _n_jolly = int((_sim['Winner'] == 'Jolly').sum())
    _n_foster = int((_sim['Winner'] == 'Foster').sum())
    _mstats = margin_stats_dem(_sim)
    _lo = np.percentile(_sim['Jolly'], 2.5) * 100
    _hi = np.percentile(_sim['Jolly'], 97.5) * 100
    _modelo_rows.append({
        'Modelo': _label,
        'P(Jolly > Foster)': format_win_prob(_n_jolly, _n_tot),
        'P(Foster > Jolly)': format_win_prob(_n_foster, _n_tot),
        'Margen mediano J-F (pts)': round(_mstats['median'], 1),
        'Margen IC95% (pts)': f"{_mstats['lo95']:.1f} a {_mstats['hi95']:.1f}",
        'Jolly IC95%': f"{_lo:.1f}%-{_hi:.1f}%",
    })
_modelo_ab_df = pd.DataFrame(_modelo_rows)
print(_modelo_ab_df.to_string(index=False))

_margin_a = margin_stats_dem(r_modelo_a['sim_results'])['median']
_margin_b = margin_stats_dem(r_modelo_b['sim_results'])['median']
_margin_gap = abs(_margin_a - _margin_b)
print(f"\nLECTURA: la diferencia en el margen mediano J-F entre Modelo A y Modelo B es de {_margin_gap:.1f} pts. "
      f"{'Ambos modelos coinciden razonablemente de cerca' if _margin_gap < 10 else 'Los modelos NO coinciden de cerca'} "
      f"-- {'consistente con que las 2 encuestas post-retiro ya dominan el peso de Modelo A (99.7%)' if _margin_gap < 10 else 'a pesar de que las 2 encuestas post-retiro dominan el peso de Modelo A, esto sugiere que las 5 encuestas antiguas SÍ mueven el resultado de forma no trivial y merece revisión adicional'}. "
      f"Con Modelo B basado en solo n=2 encuestas, su propia incertidumbre (dispersión entre encuestas, kappas) "
      f"es aún más ruidosa que la de Modelo A -- se usa como chequeo de robustez, no como forecast alternativo.")
print("=" * 70)

print("\n\n" + "=" * 70)
print("MAPEO JOSEPH DEM -- ESCENARIO A (BASE, actual) vs. ESCENARIO B (sensibilidad)")
print("=" * 70)
# FIX v8 (reemplaza al 'Modelo C' de v7 -- superado por la individualización
# de Joseph, ver DECISIÓN METODOLÓGICA v8 en celda 1; Prioridad 1 de la
# auditoría v6, 🔴 Crítica, sigue siendo la motivación de fondo): el
# notebook completo (incluido 'Modelo A' arriba) ya corre bajo
# JOSEPH_MAPPING_SCENARIO='A' -- Joseph=6 se SUMA sin tocar Other_Minor=8
# de Change Research, sin sobrescribir ningún dato original. El ÚNICO
# cuidado importante señalado por el usuario es que NO se puede asumir
# ciegamente si ese 6% ya estaba CONTENIDO dentro del Other_Minor=8
# original -- este bloque cuantifica exactamente eso, corriendo el
# Escenario B (Joseph=6 EXTRAÍDO de Other_Minor, que pasa de 8 a 2) sobre
# una COPIA del dataset (polls_dem_pre_impute NUNCA se modifica in-place)
# y comparándolo contra el Escenario A ya calculado como 'Modelo A' arriba.
# Escenario B SÍ modifica un valor original de la hoja a partir de una
# fuente secundaria sin confirmación primaria -- por eso nunca se usa como
# BASE, solo como sensibilidad explícita, exactamente como pidió el
# usuario ("no asumiría ciegamente... modelaría esa incertidumbre
# explícitamente con dos escenarios de mapeo").
polls_escenario_b_dem = polls_dem_pre_impute.copy()
_cr_mask = polls_escenario_b_dem['Poll_Source'].str.contains('Change Research', case=False, na=False)
_n_cr = int(_cr_mask.sum())
assert _n_cr == 1, f"Se esperaba exactamente 1 fila de Change Research, se encontraron {_n_cr} -- revisar."
_om_antes_cr = polls_escenario_b_dem.loc[_cr_mask, 'Other_Minor'].iloc[0]
polls_escenario_b_dem.loc[_cr_mask, 'Other_Minor'] = polls_escenario_b_dem.loc[_cr_mask, 'Other_Minor'] - 6.0
_om_despues_cr = polls_escenario_b_dem.loc[_cr_mask, 'Other_Minor'].iloc[0]
print(f"Escenario B -- fila Change Research ajustada: Other_Minor {_om_antes_cr:.0f} -> {_om_despues_cr:.0f} "
      f"(se asume que los 6 pts de Joseph YA estaban contenidos en el Other_Minor=8 original -- se extraen "
      f"en vez de sumarse). Jolly/Foster/Joseph quedan sin tocar. Todas las demás filas (incluida Targoz, "
      f"Prioridad 2 -- sin evidencia externa de error específico) quedan sin tocar.")

r_escenario_b = recompute_and_simulate_dem(poll_subset=polls_escenario_b_dem, n_simulations=10_000, seed=42)
_sim_b2 = r_escenario_b['sim_results']
_n_tot_b2 = _sim_b2.shape[0]
_n_jolly_b2 = int((_sim_b2['Winner'] == 'Jolly').sum())
_n_foster_b2 = int((_sim_b2['Winner'] == 'Foster').sum())
_n_joseph_b2 = int((_sim_b2['Winner'] == 'Joseph').sum())
_mstats_b2 = margin_stats_dem(_sim_b2)
_lo_b2 = np.percentile(_sim_b2['Jolly'], 2.5) * 100
_hi_b2 = np.percentile(_sim_b2['Jolly'], 97.5) * 100
_escenario_b_row = {
    'Escenario': "B (Joseph=6 EXTRAÍDO de Other_Minor: 8->2)",
    'P(Jolly > Foster)': format_win_prob(_n_jolly_b2, _n_tot_b2),
    'P(Foster > Jolly)': format_win_prob(_n_foster_b2, _n_tot_b2),
    'P(Joseph gana)': format_win_prob(_n_joseph_b2, _n_tot_b2),
    'Margen mediano J-F (pts)': round(_mstats_b2['median'], 1),
    'Margen IC95% (pts)': f"{_mstats_b2['lo95']:.1f} a {_mstats_b2['hi95']:.1f}",
    'Jolly IC95%': f"{_lo_b2:.1f}%-{_hi_b2:.1f}%",
}
_n_joseph_a = int((r_modelo_a['sim_results']['Winner'] == 'Joseph').sum())
_escenario_a_row = dict(_modelo_rows[0])
_escenario_a_row['Escenario'] = "A (BASE actual: Joseph=6 SUMADO, Other_Minor=8 intacto)"
_escenario_a_row['P(Joseph gana)'] = format_win_prob(_n_joseph_a, r_modelo_a['n_simulations'])
del _escenario_a_row['Modelo']
print(pd.DataFrame([_escenario_a_row, _escenario_b_row]).to_string(index=False))

_margin_b2 = _mstats_b2['median']
_margin_gap_ab2 = abs(_margin_a - _margin_b2)
print(f"\nLECTURA: entre Escenario A (BASE) y Escenario B, el margen mediano J-F pasa de {_margin_a:.1f} pts "
      f"a {_margin_b2:.1f} pts -- una diferencia de {_margin_gap_ab2:.1f} pts "
      f"({'impacto limitado' if _margin_gap_ab2 < 3 else 'impacto material'} sobre el margen J-F, "
      f"consistente con lo observado en v7 (~1.9 pts para una perturbación de magnitud similar en esta "
      f"misma fila)). El P(Joseph gana) también se compara arriba entre ambos escenarios -- se espera que "
      f"cambie proporcionalmente más que el margen J-F, porque toda la variación de 6 pts recae "
      f"directamente sobre su propio posterior (ya de por sí ancho, n=1). En ningún caso se declara un "
      f"escenario como 'correcto': el veredicto de la auditoría v6 se mantiene -- esto es una COTA de "
      f"sensibilidad bajo dos supuestos de mapeo alternativos, NO una corrección validada. Confirmar el "
      f"crosstab original de Change Research sigue siendo la única forma de resolver esto con certeza "
      f"(ver nota crítica, celda 1).")
print("=" * 70)

print("\n\n" + "=" * 70)
print("STRESS TEST PESIMISTA DEM -- TODOS LOS SUPUESTOS ADVERSOS COMBINADOS")
print("=" * 70)
# FIX v3: el stress test incorpora (a) missingness adverso de 'Other'
# (extremo ilustrativo 15%, vía el residuo reconstruido) y (b) una
# fracción del indeciso fluyendo a Other en vez de al pool de los 2
# candidatos principales. v5: se ELIMINÓ el componente 'Demings=30%' --
# ya no existe ese escenario porque no compite (ver celda 1); el stress
# adverso ahora se concentra enteramente en Foster vía priors/indecisos.
# FIX v7 (Prioridad 6 de la auditoría v6, 🟡 Baja -- título vs. contenido
# inconsistentes): el título dice "TODOS LOS SUPUESTOS ADVERSOS
# COMBINADOS", pero hasta v6 este bloque usaba undecided_to_other_share=
# 0.10 pese a que la grilla de sensibilidad (celda 6, arriba) ya prueba
# hasta 0.50 -- el verdadero extremo adverso de ese parámetro. Se sube a
# 0.50 para que el título sea literalmente cierto: cada parámetro entra
# aquí en su valor más adverso ya probado en la sensibilidad individual,
# no en un punto intermedio.
# FIX v8: undecided_center usa el mismo helper _undecided_scenario_jf()
# que la celda de sensibilidad estructural -- Joseph se mantiene en su
# valor BASE derivado (_jo0) en vez de quedar fuera del diccionario (lo
# que causaría un KeyError más abajo, porque 'posteriors' ahora tiene 3
# claves).
r_stress_dem = recompute_and_simulate_dem(
    prior_overrides=shifted_priors_adverse_dem,
    undecided_center=_undecided_scenario_jf(0.55, 0.45),
    early_vote_shift={'Jolly': -0.05, 'Foster': 0.05},
    other_avg_override=0.15,
    turnout_cv_override=0.20,
    undecided_to_other_share=0.50,
    n_simulations=10_000, seed=42,
)
sim_stress_dem = r_stress_dem['sim_results']
n_tot_stress_dem = r_stress_dem['n_simulations']
n_jolly_stress = int((sim_stress_dem['Winner'] == 'Jolly').sum())
n_foster_stress = int((sim_stress_dem['Winner'] == 'Foster').sum())
mstats_stress = margin_stats_dem(sim_stress_dem)
median_margin_stress_dem = mstats_stress['median']
lo_stress_dem = np.percentile(sim_stress_dem['Jolly'], 2.5) * 100
hi_stress_dem = np.percentile(sim_stress_dem['Jolly'], 97.5) * 100

print(f"P(Jolly > Foster):    {format_win_prob(n_jolly_stress, n_tot_stress_dem)} "
      f"({n_jolly_stress:,}/{n_tot_stress_dem:,})")
print(f"P(Foster > Jolly):    {format_win_prob(n_foster_stress, n_tot_stress_dem)} "
      f"({n_foster_stress:,}/{n_tot_stress_dem:,})")
print(f"Margen mediano J-F:   {median_margin_stress_dem:.1f} pts "
      f"(IC95% de la diferencia por simulación: {mstats_stress['lo95']:.1f} a {mstats_stress['hi95']:.1f} pts)")
print(f"Jolly IC95%:          {lo_stress_dem:.1f}%-{hi_stress_dem:.1f}%")
print(f"\nLECTURA: en el stress conjunto actualmente implementado (priors adversos, indecisos 55/45, "
      f"early vote adverso, Other=15% y 50% del indeciso fluyendo a Other -- el extremo adverso de la "
      f"grilla de sensibilidad de la celda 6), "
      f"Jolly {'gana aproximadamente ' + format_win_prob(n_jolly_stress, n_tot_stress_dem) + ' de las simulaciones' if median_margin_stress_dem > 0 else 'pierde su ventaja mediana'}. "
      f"Dado el tamaño de muestra de encuestas (n=7) y las limitaciones estructurales (sin Undecided real, "
      f"sin house effects, priors neutros), este resultado debe leerse como MENOS robusto que su "
      f"contraparte republicana -- no por peor metodología, sino por datos de entrada objetivamente más "
      f"escasos y menos completos. NOTA v5: a diferencia de v1-v4, este stress YA NO incluye un componente "
      f"'Demings=X%' -- Demings no compite, así que todo el apoyo adverso se concentra directamente en "
      f"Foster vía priors/indecisos/early vote, en vez de repartirse entre dos rivales.")
print("=" * 70)
