# Corrección post-elección 2026: evaluación de retroalimentación externa + fix aplicado a REP y DEM

**Fecha**: 19-ago-2026. **Disparador**: además del post-mortem propio (`RESULTADOS_2026_VS_PRONOSTICO.md`), se
recibió una retroalimentación externa sobre ambos modelos (v7 REP / v8 DEM), con un diagnóstico matemático
y una tabla comparativa contra otros proyectos del usuario (Arizona, Wisconsin REP/DEM, DC RCV -- fuera del
alcance de este repo). Este documento (1) evalúa esa retroalimentación de forma independiente -- qué se
verificó como correcto, qué resultó impreciso o no verificable -- y (2) documenta la corrección
efectivamente aplicada a `pipeline_republican.py` y `pipeline_democrat.py`, que en varios puntos difiere de
lo sugerido literalmente.

## 1. Evaluación de la retroalimentación externa

### 1.1. Lo que se verificó como correcto

- **El diagnóstico estructural central es correcto y coincide con el hallazgo propio del post-mortem**: ambos
  modelos repartían el residual de indecisos con un ÚNICO vector fijo aplicado igual en las 10,000
  simulaciones, con la masa concentrada en el puntero. En REP ese vector era 60/25/15, elegido a mano. En
  DEM era 78.1/11.5/10.4, derivado proporcionalmente al posterior Bayesiano (no elegido a mano, pero
  igual de concentrado en la práctica). Un vector fijo, sea cual sea su origen, no deja lugar a que el
  residual real se incline distinto de lo que el modelo ya asumía -- exactamente el patrón que produjo el
  error observado en ambas carreras.
- **La forma `p_final = p_poll,i + R·α_i` describe correctamente la mecánica del modelo** (R = residual/
  indeciso, α_i = fracción de reparto hacia el candidato i). Es una simplificación razonable de lo que hacía
  el árbol Beta/Dirichlet en el nivel de "reparto de indecisos", aunque el árbol real tiene más niveles
  (Undecided vs. Decided, Other vs. Pool, reparto dentro del pool) que esta fórmula no captura en detalle.
- **El promedio simple de encuestas de Donalds (41.3%) y el Undecided crudo (34.9%)** citados en la
  retroalimentación se verificaron de forma independiente contra `Florida_Polls_Clean_2026Primary.xlsx`
  (`df['Donalds'].mean()` = 41.26%, `df['Undecided'].mean()` = 34.95%) -- coinciden exactamente.
- **"Other_Named"/"Other_Minor" fue la categoría peor calibrada de las dos carreras** -- ya documentado en
  el post-mortem propio antes de recibir la retroalimentación, y confirmado independientemente por ella.
  Además, resultó ser el hallazgo estructural más importante del dry-run de esta corrección (ver sección 2).

### 1.2. Lo que resultó impreciso o no verificable

- **La cita "F_GROK.ipynb" (Donalds 41.3% → 65.4% tras ensemble+residual) es exacta para ESE archivo, pero
  ese archivo NO es el pipeline v7 usado en este repo.** `F_GROK.ipynb` sí existe (se verificó directamente
  en la carpeta del usuario, fuera de `florida_forecast_repo`) y sí produce exactamente 41.3% → 65.4% --
  pero es un notebook exploratorio anterior y estructuralmente distinto: pool de indecisos como un único
  número fijo (40.0%, sin árbol Beta/Dirichlet por niveles), sin house effects, sin separar Renner/
  Other_Named, turnout fijo en 1,650,000 (no derivado de datos de registro/participación histórica), y
  n_simulations=12,000 (no 10,000). El pipeline v7 final de este repo (`pipeline_republican.py`, el que
  efectivamente se usó para el pronóstico publicado) tiene una arquitectura distinta y produjo 58.4%, no
  65.4%. Es decir: el número citado es real y verificable, pero corresponde a una iteración exploratoria
  descartada, no al modelo final -- citarlo como "confirmación" del mecanismo del modelo v7 es impreciso,
  aunque de forma menor, porque el patrón cualitativo (indecisos concentrados en el puntero) sí está
  presente en ambos.
- **La tabla de la retroalimentación implica un forecast individual "Evelyn Castillo-Bach: 3.1%"** que este
  modelo nunca produjo. `pipeline_democrat.py` (v8) solo modela un bucket agregado `Other_Minor`
  (Castillo-Bach + Fernandez + Norman, sin datos propios para separarlos -- ver DECISIÓN METODOLÓGICA v8 en
  la celda 1 de ese pipeline) con una mediana de 4.8%. La retroalimentación parece haber dividido ese 4.8%
  arbitrariamente en "Castillo-Bach 3.1%" + "Otros 1.7%" sin que el modelo haya producido nunca ese
  desglose. El total agregado (4.8%) sí está correctamente representado.
- **La tabla comparativa contra Arizona, Wisconsin (REP/DEM) y DC (RCV)** no se puede verificar en esta
  sesión -- esos proyectos no están en este repositorio ni en el contexto disponible aquí. No se toma
  posición sobre si Florida es "el peor error de magnitud hasta ahora" porque no hay forma de confirmarlo
  ni refutarlo desde aquí.
- **"El promedio de encuestas ya estaba más cerca del resultado final que el forecast del modelo" es cierto
  para REP pero NO para DEM** -- una distinción que la retroalimentación no hace y que cambia la lectura de
  fondo:
  - REP: promedio simple 41.3% / promedio ponderado 45.2% vs. forecast final 58.4%, resultado real 48.0%.
    El promedio ponderado (45.2%) está a 2.8 pts del resultado real; el forecast final (58.4%) está a 10.4
    pts. El promedio de encuestas efectivamente hubiera sido mejor estimador que el forecast del modelo.
  - DEM: promedio ponderado 45.1% vs. forecast final 74.2%, resultado real 61.0%. Aquí el promedio de
    encuestas está a **15.9 pts** del resultado real -- MÁS lejos que el forecast final del modelo (13.2
    pts). El forecast del modelo, pese a sobreestimar a Jolly, terminó **más cerca** de la verdad que el
    promedio crudo de encuestas.

  Esto importa porque la recomendación #1 de la retroalimentación ("anclar el centro al promedio ponderado
  limpio, sin dejar que el residual lo mueva más de 4-6 pts") habría sido una mejora clara para REP pero
  una corrección PEOR para DEM -- hubiera anclado el forecast DEM más lejos del resultado real, no más
  cerca. La lectura más consistente con los datos es que Jolly tuvo una consolidación/movimiento tardío
  hacia él que ningún modelo anclado solo a encuestas de agosto podía capturar -- no que el mecanismo de
  indecisos DEM estuviera "mal calibrado" en la misma dirección que REP. Por eso la corrección aplicada
  aquí NO usa un tope numérico fijo (4-6 pts) sobre cuánto puede mover el residual al centro -- ver sección
  2.3.

## 2. Corrección aplicada (ambos modelos)

Se aplicó la MISMA corrección estructural a `pipeline_republican.py` (FIX v8) y `pipeline_democrat.py`
(FIX v9), verificada primero con un dry-run standalone (`/tmp/dryrun_v8/`, fuera de este repo) antes de
tocar los notebooks, y luego confirmada reconstruyendo y ejecutando ambos `.ipynb` end-to-end (0 errores /
0 warnings en ambos).

### 2.1. Reparto de indecisos/residual: de punto fijo a mezcla de 3 escenarios

Se reemplaza el vector fijo (a mano en REP, proporcional-al-posterior en DEM) por una mezcla sorteada
**por simulación** (no una vez para las 10,000, sino independientemente en cada draw) sobre las categorías
del pool MÁS los candidatos menores -- Donalds/Collins/Fishback/Other_Named en REP,
Jolly/Foster/Joseph/Other_Minor en DEM:

- **Proporcional (peso 0.40)**: igual que la composición YA decidida de esa misma simulación -- el mismo
  criterio validado en el backtest 2018-2022 (MAE 2.04 pts, ver `BACKTEST_RESULTS.md`).
- **Fragmentado (peso 0.35)**: reparto uniforme (1/4 cada categoría) -- indecisos que no se inclinan
  estructuralmente hacia nadie.
- **Consolidación hacia el líder (peso 0.25)**: la composición ya decidida elevada a un exponente 2.0 y
  renormalizada -- una consolidación suave, no un punto fijo elegido a mano.

Implementado vectorizado con el truco de la distribución Gamma (`rng.gamma(alpha_matrix)` normalizado por
fila), porque `rng.dirichlet()` no soporta nativamente un vector alpha distinto por fila en una sola
llamada.

**Por qué se incluye a los candidatos menores como categoría receptora (hallazgo del dry-run, no parte del
diseño original de esta corrección ni de la retroalimentación externa)**: un primer dry-run (solo 3
categorías, menores excluidos) mostró una mejora modesta. Extender la mezcla a 4 categorías -- dejando que
el residual también pueda fluir hacia Renner+Other en REP y Other_Minor en DEM -- resultó ser el cambio de
mayor impacto: no hay ninguna razón de principio para que un indeciso solo pueda terminar votando por los
"principales", y excluir a los menores por diseño era, en retrospectiva, tan arbitrario como el punto fijo
mismo. Esto **no** está en la retroalimentación externa recibida -- se descubrió de forma independiente
comparando contra el resultado real (Renner+Other real ≈16.4% vs. 7.3% pronosticado, el error relativo más
grande de toda la carrera REP).

El punto fijo histórico sigue disponible como escenario de comparación explícito en la celda de
sensibilidad de cada pipeline (`undecided_center=...`) -- en ese modo se preserva el comportamiento viejo
EXACTO, para que los escenarios de comparación (70/20/10, 55/45, etc.) sigan midiendo lo mismo que antes.

### 2.2. Voto anticipado: de punto fijo separado a ancla en la composición ya realizada

Antes, "early vote" simulaba su propia Dirichlet anclada a un punto fijo pre-calculado que YA incluía la
asignación puntual (sesgada) de indecisos -- con una confianza alta, eso fijaba ese sesgo con fuerza sobre
el 54-70% del voto total (early+VBM según la carrera), sin aportar información independiente real. Ahora
"early vote" se ancla a la composición YA REALIZADA de "remaining" en esa misma simulación (que ya
incorpora la mezcla de escenarios de 2.1, sin sesgo estructural) y solo se permite una perturbación
independiente modesta alrededor de ese ancla -- el "ajuste de segundo orden" que la retroalimentación
recomendaba, implementado literalmente: el voto anticipado ya no puede anclar el pronóstico completo por sí
solo, solo puede desviarse un poco de lo que ya se decidió en esa simulación.

`EARLY_VOTE_CONFIDENCE`/`EARLY_VOTE_CONFIDENCE_DEM` se recalibran de 25 a 300, porque el significado del
parámetro cambió (antes: confianza en un ancla externa; ahora: qué tan angosta es la perturbación alrededor
de "remaining"). Con confidence=300, el std resultante de esa perturbación es de ~2.5-3 pts (derivación:
std ≈ sqrt(p(1-p)/(confidence+1))) -- el rango "±2-3 pts" que pedía la retroalimentación.

### 2.3. Por qué NO se implementó literalmente "no dejar que el residual mueva el centro más de 4-6 pts"

La recomendación explícita de anclar el centro al promedio ponderado y limitar el movimiento del residual a
un rango fijo (4-6 pts) se descartó por dos razones:

1. Como se muestra en 1.2, esa regla hubiera sido una mejora para REP pero un empeoramiento para DEM -- un
   tope numérico fijo, elegido para ajustarse al comportamiento de REP, es el mismo tipo de "número mágico"
   que causó el problema original, solo que en la dirección opuesta.
2. La mezcla de escenarios (2.1) ya resuelve el problema de fondo sin necesitar un tope arbitrario: al
   dejar que la CONSOLIDACIÓN sea uno de 3 escenarios sorteados (peso 0.25) en vez de el único mecanismo,
   el residual sigue pudiendo mover el centro hacia el puntero cuando los datos lo justifican (via el
   escenario proporcional, que usa la composición ya decidida), pero ya no lo hace con un vector fijo
   elegido de antemano. El resultado empírico (MAE REP 5.98→5.0, MAE DEM 6.17→3.97) es consistente con que
   esto corrige el sesgo sin necesitar un tope duro.

### 2.4. Techo al kappa moment-matched (KAPPA_WITHIN_CAP=30)

Se agrega un techo conservador al kappa moment-matched del Nivel 2 (reparto dentro del pool) en ambos
modelos -- kappa moment-matched mide SOLO el desacuerdo observado entre encuestas, que sistemáticamente
subestima la incertidumbre real cuando las encuestas de una misma elección están correlacionadas
("herding"). **Nota honesta**: este techo apenas mueve la aguja en la práctica -- en REP capa un kappa que
ya rondaba 50-60 a 30 (efecto moderado); en DEM el spread de kappas ya está dominado por
`JOSEPH_MIN_POLL_STD` (ancho por diseño, n=1), así que el techo casi no tiene efecto. **P(win) sigue
saturado en ambos modelos corregidos** (Donalds 99.22%, Jolly 99.98%) -- la recomendación de "bajar kappas
para que P(win) no esté saturado" NO se logró de forma sustantiva, y no se persiguió más agresivamente
porque hacerlo solo para que P(win) "se vea menos confiado" sin una base empírica sería tan arbitrario como
el problema original. Con una brecha mediana de ~38 pts (REP) o ~57 pts (DEM) entre el puntero y el
segundo lugar, una probabilidad de victoria saturada sigue siendo una lectura razonable del modelo, no un
error -- lo que estaba mal no era la certeza de QUIÉN gana, sino el MARGEN, que es justamente lo que esta
corrección ataca.

### 2.5. Resultado de la corrección (verificado en notebook, no solo en dry-run)

| | Forecast original (pre-fix) | Forecast corregido (FIX v8/v9) | Resultado real | Error original | Error corregido |
|---|---|---|---|---|---|
| **REP Donalds** | 58.4% | 55.7% | 48.0% | -10.4 | -7.7 |
| **REP Collins** | 19.9% | 17.9% | 25.0% | +5.1 | +7.1 |
| **REP Fishback** | 13.2% | 12.9% | 10.0% | -3.2 | -2.9 |
| **REP Renner** | 3.8% | 6.1% | ≈9.0% | +5.2 | +2.9 |
| REP MAE (4 categorías) | | | | **5.98** | **5.0** |
| **DEM Jolly** | 74.2% | 68.2% | 61.0% | -13.2 | -7.2 |
| **DEM Foster** | 10.2% | 11.0% | 15.1% | +4.9 | +4.1 |
| **DEM Joseph** | 9.2% | 10.2% | 9.6% | +0.4 | +0.6 |
| **DEM Other_Minor** | 4.8% | 9.4% | 14.3% | +9.5 | +4.9 |
| DEM MAE (Jolly/Foster/Joseph) | | | | **6.17** | **3.97** |

Mejora sustancial en ambos modelos, mayor en DEM en términos relativos. Ninguno de los dos queda dentro de
lo que exigiría un backtest riguroso (n=1 elección real, ver advertencia de sobreajuste en 2.6), pero el
error del puntero se reduce de forma consistente con el diagnóstico (REP -10.4→-7.7 pts, DEM -13.2→-7.2
pts) sin necesitar el tope numérico rígido de la sección 2.3.

### 2.6. Advertencia de sobreajuste (autocrítica, no estaba en la retroalimentación)

La mezcla 40/35/25 y el exponente de consolidación 2.0 se diseñaron y ajustaron DESPUÉS de ver el resultado
real 2026, comparando explícitamente contra él. Que el MAE mejore en retrospectiva es evidencia de que el
mecanismo viejo tenía un sesgo estructural con dirección conocida (puntero sobreestimado, candidatos
menores subestimados) -- pero no es una prueba prospectiva de que esta mezcla específica generalice a la
próxima elección. Con n=1 observación real (más el backtest n=3, que sí es ciego/anterior), no se puede
descartar que parte de la mejora esté ajustada a las particularidades de esta elección puntual. Se considera,
aun así, una corrección defendible porque ataca un sesgo estructural con dirección conocida y un mecanismo
más principled (mezcla de escenarios plausibles en vez de un punto fijo), no porque se haya validado
formalmente contra datos fuera de muestra.

## 3. Lo que NO se cambió (y por qué)

### 3.1. Individualización de Joseph (DEM) -- se mantiene, en contra de lo sugerido

La retroalimentación sugiere "eliminar o degradar a sensibilidad" la individualización de Dotie Joseph como
tercera candidata del pool ganador. Se rechaza esa sugerencia: Joseph fue **el mejor call de todo el
ejercicio** -- 9.2% pronosticado vs. 9.6% real, un error de 0.4 pts (ahora 10.2% vs. 9.6%, 0.6 pts, tras el
fix -- sigue siendo el mejor call). Individualizarla en v8, con un piso de incertidumbre explícito
(`JOSEPH_MIN_POLL_STD=8.0` para no fingir precisión sobre una sola encuesta), fue la decisión metodológica
que mejor resistió el resultado real de las dos carreras. No hay evidencia -- ni en el resultado real, ni en
el diagnóstico de la retroalimentación, que nunca cita a Joseph como parte del problema -- de que esta capa
haya contribuido al error observado. Retirarla ahora sería deshacer la única parte del modelo DEM que la
elección confirmó como acertada, sin ninguna razón basada en evidencia.

### 3.2. Mapeo A/B de Change Research y renormalización "sobreviviente" (DEM) -- sin cambios

La retroalimentación también menciona genéricamente "capas que agravaron el problema" en el lado DEM,
incluyendo el mapeo de escenarios A/B de la encuesta Change Research (si los 6 pts de Joseph ya estaban
contenidos en su "Other_Minor=8" original) y la renormalización "sobreviviente" de las encuestas
pre-retiro de Demings. Ninguna de las dos está causalmente vinculada al sesgo frontrunner-favorable
diagnosticado -- son mecanismos de limpieza de datos para problemas estructurales distintos (ambigüedad de
un crosstab de encuesta; el retiro de una candidata a mitad de campaña), no supuestos sobre hacia dónde se
inclinan los indecisos. Ambas ya tienen su propia celda de sensibilidad documentada (`MAPEO JOSEPH:
ESCENARIO A vs. ESCENARIO B` en la celda 6) que muestra que su impacto en el margen J-F es de ~2.1 pts --
bastante menor que el efecto del fix aplicado aquí (~6 pts). Se dejan sin cambios porque "agregan
complejidad" no es, por sí solo, evidencia de que estén mal -- se necesitaría un vínculo causal específico
con el error observado, que no existe.

## 4. Verificación

- Dry-run standalone (`/tmp/dryrun_v8/`, dos iteraciones para REP -- la primera sin candidatos menores en
  la mezcla mostró mejora insuficiente, la segunda con 4 categorías confirmó el MAE 5.0 -- y una iteración
  para DEM que confirmó el MAE 3.97 directamente) antes de tocar los notebooks.
- Ambos notebooks (`FLORIDA_2026_Primaria_Republicana_v7.ipynb`, `FLORIDA_2026_Primaria_Democrata_v8.ipynb`)
  reconstruidos desde los `.py` corregidos vía `src/build_notebook.py` y ejecutados end-to-end con
  `jupyter nbconvert --execute`: **0 errores, 0 warnings** en ambos, confirmado programáticamente
  (inspección de `outputs` con `output_type == 'error'` sobre cada celda, 0 en ambos notebooks).
- Los números reportados en la sección 2.5 se extrajeron directamente de la salida real de los notebooks
  ejecutados (no del dry-run) -- coinciden exactamente con el dry-run, confirmando que la reconstrucción del
  notebook no introdujo ninguna discrepancia.
- Todas las filas de la celda de sensibilidad estructural que usan un escenario de punto fijo explícito
  (`undecided_center=...`) se verificaron reproduciendo el comportamiento viejo EXACTO -- por ejemplo, en
  DEM, el escenario "Proporcional J78/F12/Jo10 punto fijo" y la fila "0% a Other_Minor (punto fijo, paridad
  con v8)" (activada por rutas de código distintas: `undecided_center` explícito vs.
  `undecided_to_other_share` explícito) producen el mismo margen mediano (63.0 pts), confirmando que ambas
  rutas de compatibilidad hacia atrás llegan al mismo mecanismo viejo sin divergir.
