# Continuidad de auditoría: bot BTC 5m sin compras registradas

**Fecha de actualización:** 2026-11-02  
**Repositorio:** `josuemtz1088-sys/chatgpt`  
**Archivo de código auditado:** `mr_bot_v4 1.0.3.py`  
**Entorno EC2:** `~/gabagool_bot`  
**Proceso / sesión habitual:** tmux `btc`  
**Archivo local:** `mr_bot_v4.py`  
**Entorno virtual:** `.venv`

---

## 1. Objetivo y alcance

Este documento conserva el trabajo realizado desde que se reportó que el bot dejó de registrar compras, hasta la última comprobación de configuración compartida por el usuario.

La auditoría busca distinguir entre:

1. Métodos que no generan señal porque sus condiciones no se cumplen.
2. Métodos que sí pasan filtros, pero quedan detenidos antes de enviar una orden.
3. Órdenes enviadas que no se ejecutan.
4. Compras ejecutadas que no quedan reflejadas correctamente en los registros.

**Corte temporal obligatorio para el análisis de logs:** usar únicamente eventos con timestamp **desde `2026-11-02T05:30:00Z` en adelante**. Equivale a 2026-11-01 22:30 en Nayarit (UTC-7). No utilizar ciclos, eventos o ejemplos anteriores para explicar el periodo investigado. El epoch incluido en un slug identifica el inicio del mercado; no sustituye el timestamp `ts` del evento.

## 2. Confirmación del código auditado

Se comparó desde EC2 el archivo local `mr_bot_v4.py` con el contenido raw de GitHub:

- GitHub: `mr_bot_v4 1.0.3.py`
- Ruta raw: `https://raw.githubusercontent.com/josuemtz1088-sys/chatgpt/main/mr_bot_v4%201.0.3.py`
- SHA-1 EC2: `a3b068ffbaa43d3c9d3465bd74e52ddc4a578e93`
- SHA-1 GitHub: `a3b068ffbaa43d3c9d3465bd74e52ddc4a578e93`
- Comparación byte a byte: `IDENTICOS: True`

Por tanto, el archivo local y el archivo del repositorio son idénticos en el momento de esa comprobación. El hash anterior `8bf418fd1e8007eb5e4e9af268aa1da5fa0aeb9f` se había asociado equivocadamente a esta comparación; no debe usarse como referencia para esta versión.

**Límite de esta confirmación:** prueba la identidad de los archivos en disco y GitHub en el momento de la consulta. No demuestra por sí sola qué código tiene cargado en memoria un proceso Python que ya estaba iniciado, ni si ese proceso ejecuta exactamente esa ruta. Para eso hace falta verificar PID, comando y hora de inicio del proceso, y descartar que el archivo se haya cambiado después del arranque.

## 3. Evidencia de logs filtrada desde el corte temporal

El usuario compartió el resultado del diagnóstico con `--since "2026-11-02T05:30:00Z"`.

### 3.1 Eventos registrados

| Archivo | Eventos / resultados |
|---|---:|
| `book_lag.jsonl` | 659 eventos |
| `cb_log.jsonl` | 180 |
| `flow_log.jsonl` | 19 |
| `late_log.jsonl` | 95 |
| `post_loss_guard_log.jsonl` | 544 |
| `signals_log.jsonl` | 22 |
| `trades_log.jsonl` | 0 |
| `tw_log.jsonl` | 43 |
| `ds_audit_log.jsonl` | 0 |

Desglose reportado:

- **CB (180):** `CB_CVD_ADVERSE_BLOCK` 124; `CB_POST_LOSS_BLOCK` 33; `CB_SKIP_PRICE` 11; `CB_SKIP_RET` 8; `CB_SKIP_VOL60` 3; `CB_SKIP_RET_MEM` 1.
- **FLOW (19):** `FLOW_SKIP_PRICE` 10; `FLOW_POST_LOSS_BLOCK` 6; `FLOW_SKIP_VOL60` 3.
- **LATE (95):** `LATE_SKIP_PRICE` 39; `LATE_SKIP_RET` 16; `LATE_SKIP_CUSH` 16; `LATE_SKIP_VOL60` 10; `LATE_SKIP_RET_MEM` 6; `LATE_PAPER` 4; `LATE_PAPER_RESULT` 4.
- **TW (43):** `TW_SKIP_VOL60` 21; `TW_SKIP_PRICE` 17; `TW_POST_LOSS_BLOCK` 5.
- **Signals (22):** `R1_CAPTURED` 9 y varios `FAST_TRACK_REJECT` / `MULTI_ROUND_ABORT`.
- **Trades:** cero registros.

Interpretación prudente: no hay compras registradas en `trades_log.jsonl` en el conjunto filtrado. Esto no demuestra por sí solo que no se hayan intentado enviar órdenes: hay que revisar los logs de señal/ejecución y los mensajes de consola. Tampoco permite contar todos los filtros silenciosos, porque por diseño algunos retornos no escriben eventos.

### 3.2 Post-loss guard

Resumen reportado:

- FLOW CLEAR: 148.
- CB CLEAR: 147.
- TW CLEAR: 140.
- CB `CB_TRIPLE_VELOCITY_ADVERSE`: 66 bloqueos.
- TW `WAITING_FOR_SECOND_SAMPLE`: 35.
- FLOW `WAITING_FOR_SECOND_SAMPLE`: 30.
- TW `INSUFFICIENT_DATA` por ausencia de `cvd_perp_30s`: 10.
- FLOW `INSUFFICIENT_DATA` por ausencia de `cvd_perp_30s`: 8.
- FLOW `FLOW_PERSISTENT_ADVERSE`: 4.

Esto demuestra que el guard no estuvo bloqueando permanentemente: hubo numerosas evaluaciones CLEAR. Sí hubo bloqueos concretos y muestras insuficientes.

### 3.3 Volatilidad

Se reportaron algunos rechazos `SKIP_VOL60` (TW 21, FLOW 3, CB 3) y horas con sigma en régimen normal. Por tanto, la volatilidad explica parte de los descartes, pero no demuestra por sí sola una condición de bloqueo continuo durante todo el periodo.

### 3.4 Estados JSON

El snapshot compartido mostraba:

- `cb_state.json`: disabled=False, wins=0, losses=0.
- `flow_state.json`: disabled=False, wins=0, losses=0.
- `late_state.json`: disabled=False, wins=1, losses=0.
- `quiet_state.json`: disabled=False, wins=6, losses=0.
- `tw_state.json`: disabled=False, wins=17, losses=0.

Son estados actuales/snapshot, no un historial de cada instante del periodo. No deben utilizarse para afirmar qué estado tenía cada método en todos los ciclos. Los eventos `*_PAPER` de LATE son operaciones simuladas, no compras reales; el resumen no mostró eventos PAPER de TW, CB o FLOW.

## 4. Código: rutas silenciosas identificadas

La revisión se hizo sobre el archivo confirmado `mr_bot_v4 1.0.3.py`. Las condiciones siguientes pueden terminar una evaluación sin dejar un evento específico en el log del método.

### 4.1 TW — `tw_tick`

Se identificaron retornos silenciosos cuando:

- El método ya terminó el ciclo (`done`).
- Se alcanzó el máximo diario de operaciones.
- El ciclo está fuera de `TW_FROM_SEC..TW_TO_SEC`.
- Hay menos de 120 muestras DS.
- Faltan muestras para calcular PTB o el historial de sigma.
- Sigma no está disponible o el dato DS supera `TW_DS_MAX_AGE`.
- Z-score está por debajo del mínimo de régimen.
- El retroceso supera `TW_RET_MAX`.
- No hay dato de referencia para V10 o la velocidad es inferior a `TW_V10_MIN`.
- La consulta REST está dentro del throttle de 2 segundos.
- El libro REST está vacío o falla la consulta.
- El balance es insuficiente.

Algunas otras condiciones sí se registran: evento de calendario, volatilidad, sigma60, precio/top3 y post-loss guard.

### 4.2 CB y FLOW — `_SideMethod.tick`

Se identificaron retornos silenciosos cuando:

- El método no está habilitado.
- El ciclo ya está marcado como terminado.
- Se alcanzó el máximo diario (si no está en papel).
- La regla principal `self.rule(ctx)` no se cumple.
- La consulta REST está dentro del intervalo mínimo de 2 segundos.
- La consulta REST falla o devuelve un libro sin niveles.
- El balance es insuficiente.

Otros bloqueos sí se registran: CB CVD adverso UP, post-loss guard, pausa por evento, sigma/sigma60, colchón, retroceso, memoria de retroceso y precio/top3.

**CB:** tiene un filtro adicional UP: bloquea si `cvd_cb30 < -0.8` o `cvd_bn60 < -2.0`. Genera `CB_CVD_ADVERSE_BLOCK`.

**FLOW:** su regla principal exige simultáneamente PM, CVD de Binance, volumen V60, sigma mínima, Z mínimo y `ret_rel <= 0.10` (si `ret_rel` está disponible). Si no se cumple la combinación, retorna sin registrar qué condición individual falló.

### 4.3 Preparación de contexto compartido — `side_methods_tick`

CB y FLOW no llegan a evaluar sus reglas cuando:

- No hay slug válido o no hay dos tokens.
- El ciclo está fuera de `SIDE_FROM_SEC..SIDE_TO_SEC`.
- Hay menos de 60 muestras DS.
- Hay menos de 30 muestras para calcular PTB.
- El dato DS supera `SIDE_DS_MAX_AGE`.

La sigma se calcula solo si hay al menos 120 puntos históricos; si no se obtiene, puede quedar como `None` y las reglas posteriores no pasarán. El contexto se comparte entre los métodos.

### 4.4 Ejecución general

En el bucle principal, `shadow_tick()`, `tw_tick()` y `side_methods_tick()` se llaman dentro de `if USE_TREND_FOLLOW:`. Si esa variable es falsa, los tres quedan fuera de ejecución en esa rama.

Los errores de los métodos pueden ser capturados e impresos como “error ignorado”, por lo que también se debe revisar la salida de consola.

## 5. Hipótesis evaluadas hasta ahora

1. **Métodos apagados por pérdidas:** no queda demostrado para el periodo. El mercado citado anteriormente como ejemplo de pérdidas simultáneas está fuera del corte temporal y no debe usarse para explicar este intervalo. Los snapshots actuales con `disabled=False` tampoco reconstruyen el pasado.
2. **Post-loss guard:** sí bloqueó oportunidades concretas y faltó `cvd_perp_30s` en algunas evaluaciones de TW/FLOW, pero hubo muchos eventos CLEAR. No fue un bloqueo constante.
3. **Volatilidad:** hubo descartes por sigma/sigma60, pero los datos resumidos también muestran horas en régimen normal. No explica por sí sola la ausencia total de compras.
4. **Retornos silenciosos:** confirmados en el código. Es una explicación técnica plausible de por qué los logs no muestran todos los motivos, pero aún no sabemos cuántas evaluaciones del periodo terminaron por cada ruta.
5. **Orden enviada pero no ejecutada:** sigue abierta. `trades_log.jsonl=0` no descarta intentos fallidos anteriores al registro de trade. Se debe correlacionar `*_SIGNAL`, auditoría de orden, respuestas de CLOB y consola.

## 6. Configuración real: última comprobación

El usuario ejecutó primero una búsqueda anclada al inicio de línea en `env_5min_sniper.sh`; no encontró ninguna variable de la lista.

Después ejecutó una búsqueda sin ancla. La única coincidencia compartida fue:

```bash
31:export USE_TREND_FOLLOW=1
```

Esto confirma que `USE_TREND_FOLLOW` está activado en ese archivo. No confirma los valores de las demás variables ni el entorno efectivo del proceso. Pueden proceder de valores por defecto del código, de otro archivo, de variables exportadas previamente o del entorno con el que se inició el proceso.

**No asumir valores predeterminados como configuración efectiva** hasta comprobar el entorno real y el punto de arranque.

## 7. Próximas comprobaciones pendientes

Realizar de una en una, con comandos de solo lectura y compartiendo la salida:

1. Identificar PID, hora de inicio y comando del proceso real:
   ```bash
   ps -eo pid,lstart,args | grep '[m]r_bot_v4.py'
   ```
2. Confirmar si el proceso ejecuta la ruta esperada y si el archivo fue modificado después del inicio.
3. Obtener el entorno efectivo del PID para las variables relevantes (sin mostrar secretos, claves API, tokens ni credenciales).
4. Revisar en el código los valores por defecto y las variables de configuración de CB/FLOW/TW.
5. Correlacionar, solo desde el corte UTC acordado, los timestamps de:
   - `tw_log.jsonl`, `cb_log.jsonl`, `flow_log.jsonl`
   - `post_loss_guard_log.jsonl`
   - `signals_log.jsonl`, `trades_log.jsonl`
   - `ds_audit_log.jsonl`
   - `bot_output.log`
6. Determinar si hubo oportunidades que llegaron a la etapa REST, intentos `*_SIGNAL`, respuestas fallidas de CLOB o simplemente ningún candidato que superara los filtros.

## 8. Reglas de trabajo para esta auditoría

- No cambiar código, parámetros, variables de entorno, archivos, procesos ni estados sin autorización explícita.
- No reiniciar ni matar procesos.
- No tocar variables `*_PCT`.
- No borrar estados ni logs.
- Usar comandos de lectura/diagnóstico, un comando por turno cuando se solicite evidencia desde EC2.
- No afirmar que un comando se ejecutó hasta recibir su salida.
- No mezclar periodos. Todo análisis de logs para este incidente debe filtrar por `ts >= 2026-11-02T05:30:00Z`.
- Separar claramente hechos confirmados, hipótesis y comprobaciones pendientes.

---

## Estado al cierre de esta actualización

**Confirmado:** el archivo EC2 y el archivo GitHub auditado son idénticos; `USE_TREND_FOLLOW=1` aparece en el env file; el diagnóstico filtrado reportó cero trades registrados; el código contiene rutas silenciosas que pueden impedir una compra sin generar un evento explicativo.

**Pendiente:** configuración efectiva completa del proceso, identidad/ruta del proceso en ejecución, conteo de oportunidades que alcanzaron cada etapa y determinación de la causa concreta de la ausencia de compras.


## 9. Ampliación: oportunidades CB y localización del capturador de Telegram

### 9.1 Recuento CB agrupado por evento y mercado

En una consulta posterior, el usuario compartió un agrupamiento más reciente de `cb_log.jsonl`, manteniendo el filtro temporal `ts >= 1793597400` (2026-11-02T05:30:00Z). El desglose actualizado fue:

| Evento | Registros | Mercados con ese evento |
|---|---:|---:|
| `CB_CVD_ADVERSE_BLOCK` | 144 | 15 |
| `CB_POST_LOSS_BLOCK` | 34 | 9 |
| `CB_SKIP_PRICE` | 14 | 14 |
| `CB_SKIP_RET` | 12 | 12 |
| `CB_SKIP_RET_MEM` | 3 | 3 |
| `CB_SKIP_VOL60` | 4 | 4 |
| **Total** | **211** | — |

La suma correcta de los registros de esta salida es **211**, no 221. Tampoco debe sumarse la columna de mercados para obtener mercados únicos: los mismos slugs pueden aparecer en varias categorías. Este desglose sustituye al recuento anterior de 180 eventos CB para esta agrupación posterior; en particular, CVD adverse pasó de 124 a 144 en la salida más reciente. La diferencia entre ambos reportes debe conservarse como diferencia de consultas/salidas, no reconciliarse suponiendo que uno es correcto sin revisar el archivo completo.

Mercados más repetidos en `CB_CVD_ADVERSE_BLOCK` según la salida compartida:
- `btc-updown-5m-1793640900`: 20
- `btc-updown-5m-1793629800`: 18
- `btc-updown-5m-1793605800`: 14
- `btc-updown-5m-1793621100`: 14
- `btc-updown-5m-1793606100`: 13
- `btc-updown-5m-1793634000`: 12
- `btc-updown-5m-1793633100`: 10
- `btc-updown-5m-1793632200`: 8
- `btc-updown-5m-1793606700`: 8
- `btc-updown-5m-1793599500`: 6

En `CB_POST_LOSS_BLOCK`, los mercados más repetidos fueron `1793612100` (11 eventos) y `1793608800` (9). La salida del usuario también enumeró 14 mercados para `CB_SKIP_PRICE`, 12 para `CB_SKIP_RET`, 3 para `CB_SKIP_RET_MEM` y 4 para `CB_SKIP_VOL60`; algunos listados fueron abreviados en la conversación.

**Interpretación:** son registros de filtros/bloqueos, no 211 órdenes ni 211 operaciones independientes. Los eventos repetidos dentro de un mismo slug deben agruparse para analizar cada mercado, conservando a la vez el detalle temporal de cada evento. No se debe inferir el lado UP/DOWN a partir del nombre del slug ni del resultado final.

### 9.2 Cruce solicitado: lado de compra, PTB y resultado

Quedó planteado cruzar cada oportunidad CB con el archivo de resultados/mensajes de Telegram para obtener:
- mercado/slug y timestamps de cada bloqueo;
- lado que la estrategia estaba buscando comprar (UP o DOWN), leído del propio registro o del contexto de señal, no inferido;
- PTB exacto aplicado por el watcher de Polymarket;
- precio/resolución final del mercado y si ese lado habría ganado;
- relación temporal con el reinicio del proceso.

El cruce todavía **no está realizado**: no se ha leído el contenido completo de `cb_log.jsonl` ni de `result.json`. En notas previas sobre el formato del capturador se indicó que `won` no debe usarse como resultado definitivo cuando no utiliza el PTB exacto del watcher. El criterio debe basarse en el PTB exacto confirmado por el watcher y el valor de resolución/precio final correspondiente, verificando también empates y fuente temporal.

El usuario no puede adjuntar esos archivos, pero confirmó que están en EC2. Se acordó hacer el análisis directamente allí mediante comandos de solo lectura, sin copiar, mover ni alterar los archivos.

### 9.3 Proceso capturador identificado

El usuario ejecutó en EC2:

```bash
tmux list-panes -t capturador -F 'pane_pid=#{pane_pid} pane_current_path=#{pane_current_path} pane_current_command=#{pane_current_command}'
```

Salida:
- `pane_pid=1051051`
- `pane_current_path=/home/ec2-user/monitor_pasivo`
- `pane_current_command=python`

Después se comprobó que el PID del pane era el shell, no el Python:
```text
PID 1051051, PPID 3238, comando -bash
```

Con `pstree -ap 1051051` se identificó el hijo:
```text
bash,1051051
  └─python,1051125 capturar_telegram.py
```

Por tanto, el capturador real es `capturar_telegram.py`, PID **1051125**, trabajando desde `/home/ec2-user/monitor_pasivo`, dentro de la sesión tmux `capturador`. No se detuvo ni reinició.

### 9.4 Archivo de salida confirmado

El usuario inspeccionó el código con:
```bash
cd /home/ec2-user/monitor_pasivo && grep -nE 'open\\(|jsonl|result\\.json|write|append|logging|FileHandler|mkdir|makedirs|Path\\(' capturar_telegram.py
```

Salida compartida:
```text
13:OUTPUT_FILE = BASE_DIR / "telegram_eventos.jsonl"
55:        with OUTPUT_FILE.open("a", encoding="utf-8") as archivo:
56:            archivo.write(
```

Esto confirma que el capturador define el archivo de salida como **`/home/ec2-user/monitor_pasivo/telegram_eventos.jsonl`** (BASE_DIR corresponde al directorio del script) y lo abre en modo append (`"a"`), escribiendo eventos en JSONL. No se ha confirmado todavía que exista un archivo llamado `result.json` en ese directorio ni que ese sea el nombre del archivo que contiene los PTB/resoluciones. Tampoco se ha inspeccionado el formato completo de cada registro.

### 9.5 Siguiente paso operativo

Continuar desde EC2 con una sola instrucción de lectura por turno:
1. Inspeccionar de forma segura el resto de `capturar_telegram.py` para entender el esquema de `telegram_eventos.jsonl` y cómo se serializan los mensajes.
2. Localizar, primero dentro de `/home/ec2-user/monitor_pasivo` y `/home/ec2-user/gabagool_bot`, los archivos de resultados/Telegram relevantes, sin imprimir secretos ni el contenido completo de mensajes potencialmente sensibles.
3. Extraer solo campos necesarios y cruzarlos con los eventos CB que cumplan `ts >= 1793597400`.
4. Para comprobar si cada evento fue posterior al reinicio, comparar su timestamp `ts` con la hora exacta de inicio del proceso bot. El dato reportado hasta ahora es `Mon Nov 2 05:34:54 2026`, pero antes de usarlo como UTC se debe confirmar la zona horaria del servidor. El corte general de auditoría sigue siendo 05:30:00Z; no confundirlo con la hora de reinicio.
5. No confundir el epoch del slug con el timestamp del evento ni con el reinicio.

**Estado:** ya se localizó el mecanismo de captura y su archivo JSONL. El cruce de lado, PTB exacto, resultado final y posterioridad al reinicio continúa pendiente de extraer los registros reales.
