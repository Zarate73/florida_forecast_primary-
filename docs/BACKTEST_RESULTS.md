# Backtest 2018 / 2022 — validación externa del pipeline de pronóstico

## Por qué existe este documento

Hasta esta versión, los datos 2018/2022 del repositorio (`Florida_Governor_Primaries_2018_2022.xlsx`,
`Florida_Governor_Primary_Turnout_2018_2022.xlsx`) se usaban **únicamente** para calibrar el submodelo
de turnout esperado (participación total, CV del turnout). En ningún punto del pipeline se validaba si
la maquinaria de pronóstico en sí misma — ponderación de encuestas por time-decay, ensamble Bayesiano,
árbol de composición Beta/Dirichlet moment-matched — habría acertado en una elección real. Este
documento cierra parcialmente ese hueco corriendo esa misma maquinaria sobre encuestas reales de tres
primarias de gobernador de Florida ya resueltas.

**Actualización 19-ago-2026**: la primaria de gobernador 2026 ya se realizó (18-ago-2026), así que ahora
existe además una validación DIRECTA (no un backtest reconstruido) del pronóstico real contra el
resultado real — ver [`RESULTADOS_2026_VS_PRONOSTICO.md`](RESULTADOS_2026_VS_PRONOSTICO.md). No se fusiona
esa observación en la tabla de este documento porque usa una condición metodológica distinta: este
backtest corre con prior neutro y reparto de indecisos proporcional (para no meter lookahead bias),
mientras que los modelos 2026 usaron sus propios priors/reparto de indecisos reales (subjetivo en REP,
proporcional-concentrado en DEM) — mezclarlas en la misma tabla compararía dos metodologías distintas
como si fueran una sola medición. Son dos ejercicios complementarios, no una sola serie de n=4.

**Alcance real de esta validación: léase antes de citar cualquier número de aquí.** Solo hay **3
elecciones primarias históricas comparables** disponibles para este backtest específico (Florida elige
gobernador cada 4 años; 2018 tuvo primaria competitiva en ambos partidos, 2022 solo la tuvo en el lado
demócrata — el REP 2022 no tuvo contienda real, DeSantis corrió sin oposición efectiva). Con n=3 **no es
posible calibrar** el modelo en el sentido
estadístico estricto (no se puede estimar, por ejemplo, si un intervalo de confianza del 90% cubre el
resultado real el 90% de las veces con 3 observaciones). Lo que sí permite este ejercicio es una **prueba
de sanidad direccional**: corriendo el modelo de forma honesta, solo con información disponible ANTES
del día de cada elección, ¿habría señalado como más probable al candidato que efectivamente ganó?, y
¿qué tan lejos habría quedado el punto estimado del resultado real?

## Resultado agregado

| Carrera | Encuestas usadas | Ganador real | Top-pick del modelo | ¿Acertó? | P(gana) asignada al ganador real | MAE (pts) |
|---|---|---|---|---|---|---|
| REP 2018 — DeSantis vs. Putnam | 18 | DeSantis | DeSantis | **SÍ** | 85.8% | 0.77 |
| DEM 2018 — Gillum/Graham/Levine/Greene/King | 21 | Gillum | Graham | **NO** | 9.6% | 4.45 |
| DEM 2022 — Crist vs. Fried | 10 | Crist | Crist | **SÍ** | 93.8% | 0.91 |

**2 de 3 aciertos direccionales.** El fallo (DEM 2018) no es un bug del modelo: es la primaria demócrata
de gobernador más citada como "sorpresa frente a las encuestas" en la historia reciente de Florida.
Gwen Graham lideró la enorme mayoría de las encuestas durante toda la campaña (incluida la última,
St. Pete Polls 25-26 ago: Graham 32% vs. Gillum 25%, un margen de 7 puntos a solo 2 días de la elección);
Andrew Gillum ganó igual, por 2.2 puntos sobre Graham. En su momento, tanto RealClearPolitics como los
principales agregadores de encuestas dieron esa carrera como favorable a Graham hasta el cierre — este
modelo comete exactamente el mismo error que cometió el consenso de encuestas en tiempo real, porque
depende de la misma fuente de información (encuestas) y no tiene ningún mecanismo para anticipar un giro
de última hora en la participación/composición del electorado que las encuestas no captaron. Es una
limitación real y documentada del enfoque "solo-encuestas", no un error de implementación — de hecho, es
tranquilizador que el modelo NO le haya dado 0% de probabilidad a Gillum (le dio 9.6%, reconociendo la
incertidumbre real de la carrera) en vez de una falsa certeza sobre Graham.

## Metodología

**Qué SÍ es idéntico al pipeline 2026 vigente** (ver `src/backtest/backtest_engine.py`, que reimporta
literalmente las mismas fórmulas, no una reinterpretación):
- `extract_end_date()`: mismo parser de rangos de fecha ("Mon D–D, YYYY" / "Mon D – Mon D, YYYY").
- `Poll_Weight = Sample * exp(-ln(2)/half_life * Days_Since_Poll)`, con `half_life=14` — el **mismo**
  valor que usan los modelos 2026, sin recalibrar con los datos históricos (recalibrarlo ahora, sabiendo
  el resultado, sería sobreajustar el hiperparámetro a la respuesta ya conocida).
- `weighted_average()` / `poll_dispersion()`: idénticas.
- `bayesian_update()`: la misma actualización Normal-Normal conjugada por precisión inversa.
- Árbol de composición Beta/Dirichlet moment-matched: Nivel 0 (Undecided vs. Decided, Beta ajustada por
  momentos) + Nivel 1 (reparto dentro de Decided vía Dirichlet moment-matched, con
  `kappa = mediana(kappas implícitas por candidato)` — el mismo criterio que `kappa_within` en ambos
  pipelines 2026).

**Qué NO replica, y por qué (cada decisión busca evitar lookahead bias, no simplificar por comodidad):**
- **House effects por encuestadora**: no existen house effects documentados para pollsters de 2018/2022
  en este proyecto — inventarlos ahora, conociendo el resultado, sería la forma más directa de
  contaminar el backtest con información posterior. Se corre sin ajuste de house effects.
- **Early vote / turnout día-a-día**: los modelos 2026 separan "ya votado temprano" de "falta por votar"
  con datos de early vote 2026 que no existen con el mismo detalle para 2018/2022. El backtest pronostica
  el voto final total directamente desde encuestas.
- **Prior subjetivo/fundamentales**: en 2026-REP el prior es un juicio declarado del analista antes de
  ver resultados. Para 2018/2022 no existe ese juicio histórico documentado, y construirlo ahora
  (sabiendo que ganó Gillum, que ganó Crist...) sería lookahead bias explícito. Se usa el mismo prior
  **neutro** que ya usa el modelo DEM 2026 v8 (centrado en el propio promedio de encuestas,
  `NEUTRAL_PRIOR_STD=0.30` — 30 puntos de ancho, tan difuso que en la práctica es casi un no-op: el dato
  domina casi por completo, que es la decisión correcta cuando no hay un prior verdaderamente
  independiente del resultado ya conocido).
- **Reparto de indecisos**: en vez de un supuesto de reparto declarado a mano (como en los modelos 2026),
  aquí los indecisos se reparten proporcionalmente a la composición ya estimada del bloque decidido en
  cada simulación — el supuesto neutro estándar cuando no hay encuesta de "hacia dónde se inclinan los
  indecisos".
- **Candidatos con una sola encuesta** ("Other" en DEM 2022, con 1 encuesta): se les aplica el mismo piso
  de desviación estándar (`MIN_POLL_STD=8.0` puntos) que usa `JOSEPH_MIN_POLL_STD` en el modelo DEM 2026
  v8 para Dotie Joseph — mismo criterio, mismo valor, aplicado por la misma razón (una sola medición no
  alcanza para estimar dispersión propia).

## Datos: encuestas históricas usadas

`data/Historical_Polls_2018_2022.xlsx` (generado por `src/backtest/build_historical_polls.py`), 3 hojas:
`REP_2018` (18 encuestas usadas, tras cortar en 1-jun-2018), `DEM_2018` (21 encuestas, mismo corte),
`DEM_2022` (10 encuestas, corte 1-jun-2022).

**Fuente**: tablas de "opinion polling" de los artículos de Wikipedia *2018 Florida gubernatorial
election* y *2022 Florida gubernatorial election*, a su vez trazables a RealClearPolitics/RealClearPolling
y a la cobertura de prensa contemporánea de cada encuesta (St. Pete Polls, Mason-Dixon, GBAO, University
of North Florida, Florida Atlantic University/BEPI, SurveyUSA, Public Policy Polling, Change Research,
entre otras).

**Advertencia de procedencia — importante**: esta tabla se construyó con una extracción automatizada de
una página web (no un archivo estructurado descargado directamente de cada encuestadora o de la API de
RCP), seguida de limpieza manual documentada en el docstring de `build_historical_polls.py` (corrección
de un typo de año, eliminación de 2 filas sin precisión de día, deduplicación de 2 filas repetidas/casi
repetidas). Como verificación de sanidad cruzada: el resultado agregado reproduce correctamente un hecho
histórico bien documentado e independiente de esta fuente (que Gillum ganó pese a estar sistemáticamente
por detrás de Graham en encuestas, incluida la última) — eso es consistente con que los números
individuales sean sustancialmente correctos, pero **no es una garantía cifra-por-cifra**. Si este backtest
se va a citar externamente o se va a usar para ajustar hiperparámetros de producción, se recomienda
re-verificar las filas directamente contra los comunicados/PDFs originales de cada encuestadora antes de
tratarlas como definitivas.

## Cómo reproducir

```bash
cd data/
python3 ../src/backtest/build_historical_polls.py   # reconstruye Historical_Polls_2018_2022.xlsx
python3 ../src/backtest/backtest_engine.py           # corre las 3 carreras y muestra la tabla completa
```

## Qué NO demuestra este backtest (para no sobre-interpretarlo)

- No calibra el modelo (n=3, ver arriba).
- No valida los hiperparámetros específicos de 2026 (candidatos, priors subjetivos, house effects,
  modelo de early vote) — esos no se ejercitan aquí en absoluto.
- No valida el submodelo de turnout/early-vote del pipeline 2026 (fuera de alcance de este backtest,
  ver "Qué NO replica" arriba).
- Un 2/3 de aciertos direccionales con n=3 tiene un intervalo de confianza gigantesco — no es evidencia
  fuerte de que el modelo acierte "2 de cada 3 veces" en general. Es evidencia de que el modelo se
  comporta de forma razonable y consistente con el consenso de encuestas de cada momento, con el error
  esperable cuando ese consenso mismo se equivocó.
