# Primaria real 2026 vs. pronóstico (v7 REP / v8 DEM)

Elección: 18-ago-2026. Resultados a **99.2% de las precintas reportadas** (fuente: News4Jax, cifras
consistentes con las publicadas por WFTV a 92% de conteo — la brecha entre ambos cortes es pequeña,
señal de que el conteo ya estaba estabilizado). No son cifras certificadas oficialmente todavía, pero a
este nivel de conteo el margen de variación remanente es mínimo. **AP proyectó ganador en ambas primarias
la noche de la elección**: Byron Donalds (REP) y David Jolly (DEM).

Dato estructurado (votos y % por candidato, proveniencia completa, y qué falta certificar) en
`data/Florida_Governor_Primary_2026_Results.xlsx` — generado por `src/results/build_2026_results.py`.
Las cifras de este documento son las mismas que ese archivo, no una fuente independiente.

> **Nota (19-ago-2026)**: las cifras de "Mediana pronosticada" de este documento son las del pronóstico
> **ORIGINAL pre-elección** (última corrida 17-ago-2026), el que se compara aquí contra el resultado real.
> Los notebooks (`notebooks/*.ipynb`) YA NO reproducen exactamente estos números -- tras este post-mortem
> se aplicó una corrección metodológica al reparto de indecisos (ver
> [`docs/CORRECCION_POST_ELECCION_2026.md`](CORRECCION_POST_ELECCION_2026.md)) y se re-ejecutaron. Este
> documento se deja intacto como el registro del pronóstico original que efectivamente se hizo antes de
> conocer el resultado -- no se retocan sus números para que coincidan con la versión corregida.

## Resultado agregado: ambos ganadores acertados, ambos márgenes sobreestimados

| | Ganador real | Top-pick del modelo | ¿Acertó? | P(gana) asignada | Mediana pronosticada | Resultado real | Error |
|---|---|---|---|---|---|---|---|
| REP | Donalds | Donalds | **SÍ** | 99.94% | 58.4% | 48.0% | **-10.4 pts** |
| DEM | Jolly | Jolly | **SÍ** | >99.97% | 74.2% | 61.0% | **-13.2 pts** |

**2 de 2 aciertos direccionales** (consistente con el 2/3 del backtest 2018/2022, ver
`docs/BACKTEST_RESULTS.md`). Pero en ambas carreras, **de forma independiente y en la misma dirección**,
el modelo sobreestimó al puntero y subestimó a todo el resto del campo. Esto no es ruido aleatorio — es
un patrón sistemático que apunta a la misma causa en los dos modelos: el supuesto de reparto de
indecisos.

## Tabla completa

### Republicana

| Candidato | Mediana pronosticada | IC95% pronosticado | Resultado real | Error (pts) | ¿Real dentro del IC95%? |
|---|---|---|---|---|---|
| Donalds | 58.4% | 46.8% – 69.3% | 48.0% | -10.4 | Sí (al borde inferior) |
| Collins | 19.9% | 11.9% – 30.5% | 25.0% | +5.1 | Sí |
| Fishback | 13.2% | 7.0% – 22.6% | 10.0% | -3.2 | Sí |
| Renner | 3.8% | 1.7% – 8.3% | ≈9.0% | +5.2 | No (al borde, +0.7 pts fuera) |
| Otros (7 candidatos menores) | 3.5% | 1.5% – 7.8% | ≈8.0% | +4.5 | No (al borde, +0.2 pts fuera) |

MAE (Donalds/Collins/Fishback/Renner): **5.98 pts** — casi 3x el MAE promedio del backtest histórico
(2.04 pts, n=3 elecciones 2018/2022 con la misma metodología).

### Demócrata

| Candidato | Mediana pronosticada | IC95% pronosticado | Resultado real | Error (pts) | ¿Real dentro del IC95%? |
|---|---|---|---|---|---|
| Jolly | 74.2% | 60.0% – 85.0% | 61.0% | -13.2 | Sí (al borde inferior) |
| Foster | 10.2% | 4.1% – 21.3% | 15.1% | +4.9 | Sí |
| Joseph | 9.2% | 3.3% – 20.1% | 9.6% | **+0.4** | Sí (muy cerca del centro) |
| Other_Minor (Castillo-Bach + Fernandez + Norman) | 4.8% | 1.3% – 14.0% | 14.3% | +9.5 | No (al borde, +0.3 pts fuera) |

MAE (Jolly/Foster/Joseph): **6.17 pts**.

## Lectura

**1. La individualización de Joseph (v8) fue la apuesta correcta.** Con una sola encuesta (Change
Research, 6%) y un piso de incertidumbre explícito (`JOSEPH_MIN_POLL_STD=8.0`), el modelo predijo 9.2%
para Joseph — el resultado real fue 9.6%, un error de solo 0.4 puntos, el mejor call de todo el ejercicio
y muy superior a cómo le habría ido a Joseph escondida dentro de un "Other_Minor" agregado (que sí quedó
mal calibrado, ver punto 3). Este es el resultado que justifica retrospectivamente la decisión de
separarla en v8 en vez de dejarla en la v7.

**2. Ambos modelos, de forma independiente, sobreestimaron al puntero y subestimaron al resto —
la causa más probable es el reparto de indecisos, no la ponderación de encuestas en sí.** El REP asignó
indecisos 60/25/15 (Donalds/Collins/Fishback, elegido a mano, con "confianza declarada baja" según su
propia alerta metodológica). El DEM los repartió proporcional a Jolly:Foster:Joseph (78.1%/11.5%/10.4%),
igual de concentrado en el puntero. En ambas carreras el resultado real movió la aguja EN CONTRA del
puntero relativo a esa asignación — exactamente el patrón que se vería si los indecisos reales se
inclinaron más parejo (o incluso en contra) del líder de lo que ambos modelos asumieron. El backtest
2018/2022 (que reparte indecisos proporcional al bloque ya decidido, sin sesgo hacia nadie) tuvo un MAE
promedio de 2.04 pts — bastante menor que los 5.98/6.17 pts de esta elección real, lo cual es consistente
con esta hipótesis, aunque con n=1 elección por lado no se puede confirmar estadísticamente.

**3. "Other_Minor"/"Otros" fue, en ambos lados, la categoría peor calibrada.** Son candidatos con cero o
casi cero polling individual — el modelo los trata correctamente como de alta incertidumbre (por eso el
IC95% de esa categoría es ancho en ambos casos), pero el punto central (mediana) fue el más alejado del
resultado real en términos relativos (DEM: mediana 4.8% vs. real 14.3%, casi 3x subestimado). Con datos
así de escasos, esto es más una limitación estructural de la información disponible que un error de
implementación — no había con qué estimar mejor esa categoría antes de la elección.

**4. Las probabilidades de victoria (P(gana)) fueron correctas en dirección pero, como es esperable con
carreras tan lopsided en el pronóstico, estaban "saturadas" cerca de 100%/0% y no aportan señal fina —
el número que sí importaba vigilar (y el que más se equivocó) era el margen mediano, tal como advertía la
propia celda de sensibilidad de cada notebook** ("la métrica informativa es el margen mediano, no
P(gana) saturada").

## Qué revisar antes de la próxima elección

- ~~Recalibrar el reparto de indecisos con datos reales (encuestas con cross-tabs de "hacia dónde se
  inclinan" los indecisos, o encuestas de "segunda opción") en vez de una asignación a mano o
  proporcional simple — es el hiperparámetro que más explica el error observado aquí.~~ — parcialmente
  hecho (19-ago-2026): sin cross-tabs reales disponibles, se reemplazó el punto fijo por una mezcla de 3
  escenarios plausibles (proporcional/fragmentado/consolidación) en vez de datos de "segunda opción" que
  no existen para esta elección — ver `docs/CORRECCION_POST_ELECCION_2026.md` para el detalle completo,
  incluida una autocrítica de sobreajuste (la mezcla se calibró viendo ya este resultado) y la evaluación
  de una retroalimentación externa recibida sobre ambos modelos. La recomendación de fondo (datos reales de
  cross-tabs de indecisos) sigue pendiente para una próxima elección — no existe forma de generarlos
  retroactivamente para 2026.
- Considerar si el patrón "puntero sobreestimado" es un sesgo genérico de encuestas de primarias con
  campo fragmentado (consolidación tardía de indecisos hacia los no-punteros, un patrón documentado en la
  literatura de primarias) y, si se confirma con más datos, aplicar una corrección sistemática en vez de
  esperar que el promedio de encuestas por sí solo lo capture.
- ~~Sumar esta elección al backtest de `docs/BACKTEST_RESULTS.md` como observación adicional~~ — hecho
  (19-ago-2026): se agregó como validación DIRECTA separada, no fusionada a la tabla de n=3 del backtest
  histórico, porque usa una condición metodológica distinta (prior/reparto de indecisos reales de cada
  modelo, no el motor neutro del backtest) — ver la nota "Actualización 19-ago-2026" al inicio de
  `docs/BACKTEST_RESULTS.md`. Contando ambas fuentes el n efectivo sube a 4, todavía insuficiente para
  calibrar formalmente, pero cada punto ayuda.
- Actualizar `data/Florida_Governor_Primary_2026_Results.xlsx` con el canvass oficial certificado cuando
  el Florida Division of Elections lo publique (~10 días post-elección) — el dato actual es preliminar
  (99.2% de precintas), y el bucket "Other_Minor" del lado REP es un estimado por resta, no un conteo
  directo (ver hoja `Metadata` del archivo para el detalle).
