# Forecast Primarias Florida 2026 (Gobernador)

Modelos de pronóstico probabilístico (encuestas + Monte Carlo Bayesiano/Dirichlet) para las primarias de gobernador de Florida 2026, lado **Republicano** (v7, final) y **Demócrata** (v8, final).

Ambos modelos comparten arquitectura: ponderación de encuestas por time-decay, ensamble Bayesiano conjugado-normal (prior neutro/subjetivo + datos de encuestas), y una simulación Monte Carlo con un árbol de composición Beta/Dirichlet de varios niveles (cada nivel con su propio parámetro de concentración, en vez de una única Dirichlet compartida).

## Estructura del repo

```
data/                           Insumos crudos (encuestas, early vote, turnout histórico)
├── Florida_Polls_Clean_2026Primary.xlsx
├── Florida_EarlyVoting_Joined_2026Primary.xlsx
├── Florida_Governor_Primary_Turnout_2018_2022.xlsx
├── Florida_Governor_Primaries_2018_2022.xlsx
├── Historical_Polls_2018_2022.xlsx   Encuestas individuales reales 2018/2022 (insumo del backtest)
└── Historico/                  Resultados oficiales 2018/2022 (texto plano, fuente del turnout histórico)

src/
├── cell0_historical.py         Celda 0 común a ambos notebooks: extrae resultados históricos 2018/2022
├── build_notebook.py           Reconstruye el .ipynb ejecutable a partir del pipeline plano (ver más abajo)
├── republican/
│   └── pipeline_republican.py  Pipeline republicano v7 (fuente de verdad, script plano)
├── democrat/
│   └── pipeline_democrat.py    Pipeline demócrata v8 (fuente de verdad, script plano)
└── backtest/
    ├── build_historical_polls.py   Construye Historical_Polls_2018_2022.xlsx
    └── backtest_engine.py          Corre la misma metodología del pipeline sobre 2018/2022 (ver docs/BACKTEST_RESULTS.md)

notebooks/
├── FLORIDA_2026_Primaria_Republicana_v7.ipynb   Notebook final republicano (ejecutado, 0 errores/0 warnings)
└── FLORIDA_2026_Primaria_Democrata_v8.ipynb     Notebook final demócrata (ejecutado, 0 errores/0 warnings)

docs/
└── BACKTEST_RESULTS.md         Backtest 2018/2022: metodología, resultados y límites (n=3 elecciones)
```

Los `.ipynb` en `notebooks/` son la versión **final publicable**, ya ejecutados end-to-end. Los `.py` en `src/` son la fuente canónica: cada `.ipynb` se generó automáticamente a partir de su `.py` correspondiente vía `build_notebook.py` (ver abajo), así que cualquier cambio futuro debe hacerse en el `.py`, no editando el notebook a mano.

## Cómo reproducir

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Reconstruir el .ipynb desde el pipeline plano (sin ejecutar)
python3 src/build_notebook.py \
    --pipeline src/democrat/pipeline_democrat.py \
    --output notebooks/FLORIDA_2026_Primaria_Democrata_v8.ipynb

python3 src/build_notebook.py \
    --pipeline src/republican/pipeline_republican.py \
    --output notebooks/FLORIDA_2026_Primaria_Republicana_v7.ipynb

# Ejecutar y verificar (correr con cwd = data/, o copiar los .xlsx/Historico/
# al directorio de ejecución -- el pipeline los lee por nombre relativo)
cd data/
jupyter nbconvert --to notebook --execute --output ../notebooks/FLORIDA_2026_Primaria_Democrata_v8.ipynb \
    ../notebooks/FLORIDA_2026_Primaria_Democrata_v8.ipynb --ExecutePreprocessor.timeout=180
```

Verificación esperada: 0 celdas con `output_type == 'error'`, 0 stderr con "Warning"/"Error", `execution_count` secuencial 1-7.

## Metodología (resumen)

**Ponderación de encuestas**: time-decay exponencial (`half_life=14` días, mismo hiperparámetro en ambos modelos, no recalibrado independientemente) sobre el tamaño de muestra de cada encuesta.

**Ensamble Bayesiano**: por candidato, `posterior = combinación por precisión inversa de un prior y el promedio ponderado de encuestas`. En el lado republicano el prior es subjetivo (fundamentales declarados por el analista); en el demócrata es neutro (centrado en el propio promedio de encuestas, con desviación estándar deliberadamente ancha) porque no existe un juicio de fundamentales documentado para esa contienda.

**Composición Monte Carlo**: árbol de splits Beta/Dirichlet "moment-matched" (la Beta/Dirichlet cuya media y varianza coinciden con las estimadas de los datos) en vez de una única Dirichlet global — evita que categorías de confianza muy distinta (p. ej. una encuesta vs. un candidato con una sola medición) compartan el mismo parámetro de concentración.

**Demócrata v8 — estructura de candidatos**: `winner_pool = ['Jolly', 'Foster', 'Joseph']`, con `Other_Minor` (Castillo-Bach + Fernandez + Norman, agregados por falta de polling individual) fuera del pool ganador. Dotie Joseph se individualiza a partir de una única medición de polling (Change Research, 6%) más cobertura editorial (AP) que la nombra junto a Jolly y Foster entre los 6 demócratas calificados — su incertidumbre se trata con un piso explícito (`JOSEPH_MIN_POLL_STD`) varias veces más ancho que el de Jolly/Foster, precisamente porque descansa en una sola observación.

**Riesgo de mapeo de datos (Change Research)**: existe evidencia secundaria (no primaria) de que el 6% de Joseph en Change Research podría no estar reflejado, o podría ya estar contenido, en el valor de `Other_Minor=8` de esa misma fila. El notebook **no sobrescribe el dato original** — cuantifica el impacto de ambas hipótesis explícitamente en la celda 6 ("MAPEO JOSEPH: ESCENARIO A vs. ESCENARIO B") sin declarar ninguna como correcta. Ver el bloque de comentarios "RIESGO DE MAPEO DE DATOS" al inicio de `pipeline_democrat.py` para el detalle completo con fuentes.

## Backtest 2018 / 2022

`src/backtest/` corre la MISMA metodología nuclear (time-decay half_life=14, ensamble Bayesiano, árbol Beta/Dirichlet moment-matched) sobre encuestas reales de las 3 primarias de gobernador de Florida comparables ya resueltas (REP 2018 DeSantis-Putnam, DEM 2018 Gillum-Graham-Levine-Greene-King, DEM 2022 Crist-Fried) y compara el pronóstico contra el resultado real. Resultado: **2 de 3 aciertos direccionales**, MAE promedio 2.04 pts; el fallo (DEM 2018) reproduce la conocida "sorpresa Gillum" — todas las encuestas, incluida la última a 2 días de la elección, daban a Graham como líder. Detalle completo, metodología, qué SÍ y qué NO replica del pipeline 2026, y por qué (evitando lookahead bias en cada decisión), en [`docs/BACKTEST_RESULTS.md`](docs/BACKTEST_RESULTS.md) — **léase antes de citar cualquier cifra de ese backtest**, en particular la sección sobre por qué n=3 no permite calibrar el modelo, solo una prueba de sanidad direccional.

## Limitaciones y advertencias (leer antes de citar cualquier número)

- Ninguna probabilidad de este modelo es una probabilidad electoral calibrada: son probabilidades **condicionales al modelo** (a sus supuestos de ponderación, priors e imputación). Existe un backtest direccional contra 3 primarias reales de Florida (2018 REP, 2018 DEM, 2022 DEM) — ver sección "Backtest 2018/2022" arriba — pero n=3 no alcanza para una calibración estadística real.
- El lado demócrata tiene un orden de magnitud menos de encuestas que el republicano (7 vs. 39 tras deduplicar) — toda estimación es proporcionalmente más ruidosa.
- No existe columna "Undecided" real en ninguna de las dos hojas de encuestas; se infiere como residuo, con las limitaciones que eso implica (documentadas extensamente en la celda 1 de cada pipeline).
- Cada notebook imprime, en su celda 5, una lista completa de advertencias metodológicas (`methodology_warnings`) — es la fuente de verdad sobre limitaciones vigentes, más actualizada que este README.

## Historial de versiones

**Republicano** (`pipeline_republican.py`, v1→v7): correcciones progresivas de parseo de fechas, separación del árbol de composición en niveles Beta/Dirichlet con kappa propio por nivel (en vez de una Dirichlet global de 6 categorías), corrección del sesgo de "Other_Named" con encuestas pareadas, ajustes de house effects por encuestadora, y adición de la celda de sensibilidad de hiperparámetros (tornado + escenarios estructurales + stress test).

**Demócrata** (`pipeline_democrat.py`, v1→v8): v1-v4 modelaban a Jerry Demings como candidata activa; v5 la retira del pool tras confirmar su retiro de campaña (5-jun-2026) vía fuentes primarias y un chequeo de consistencia con los propios datos (split temporal perfecto de missingness). v6 corrige que su apoyo histórico medido caía por error dentro del residuo de indecisos, y añade renormalización "sobreviviente" para las encuestas pre-retiro. v7 corrige mezcla de escalas entre el residuo y el promedio renormalizado, hace autocontenido el prior de un modelo de validación restringido a encuestas post-retiro, amplía la sensibilidad del residuo hacia candidatos menores, y documenta (sin resolver unilateralmente) un riesgo de mapeo de datos en la encuesta Change Research. v8 individualiza a Dotie Joseph como tercera candidata del pool ganador -- antes agregada dentro de "Other" -- con su propio tratamiento de incertidumbre y los dos escenarios de mapeo mencionados arriba.

Cada versión fue auditada de forma adversarial (rúbrica numérica + hallazgos priorizados) antes de avanzar a la siguiente; los notebooks intermedios (v1-v6/v7) no se incluyen en este repositorio -- solo las versiones finales v7 (REP) y v8 (DEM).

**Post-publicación**: se agregó `src/backtest/` (encuestas reales 2018/2022 + motor de backtest que reutiliza la misma metodología del pipeline) tras identificarse que los datos 2018/2022 existentes solo alimentaban el submodelo de turnout y nunca validaban el mecanismo de pronóstico en sí. Ver `docs/BACKTEST_RESULTS.md`.
