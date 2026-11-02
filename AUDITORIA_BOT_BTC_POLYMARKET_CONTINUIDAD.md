# Documento de continuidad — Auditoría del bot BTC Up/Down 5m (Polymarket)

**Propósito:** permitir que una nueva conversación retome la auditoría sin volver a descubrir el contexto, las rutas, los datos ya procesados ni las precauciones metodológicas.

**Estado:** análisis histórico en curso. Este documento no autoriza cambios en el bot ni operaciones.

---

## 1. Objetivo de la auditoría

Auditar con evidencia histórica el bot de Polymarket que opera mercados BTC Up/Down de 5 minutos. Buscamos entender:

1. Qué señales reales generaron TW, FLOW y CB.
2. Qué señales se rechazaron y por qué.
3. Qué habría ocurrido direccionalmente con los rechazos.
4. Si esas oportunidades tenían precio y liquidez razonablemente ejecutables.
5. Cómo cambian los resultados por estrategia, sigma, precio de contrato, tiempo transcurrido y condiciones de mercado.
6. Si hay exposición correlacionada cuando varias estrategias actúan en el mismo mercado de 5 minutos.
7. Qué filtros merecen una evaluación posterior, sin optimizar de más ni modificar parámetros con evidencia insuficiente.

La prioridad inmediata es recuperar la dirección de los **144 eventos SKIP_VOL con sigma entre 4 y 6**, especialmente los 94 eventos TW que no registran side UP/DN.

## 2. Límites y reglas obligatorias

- Todo el trabajo de extracción y análisis debe hacerse localmente en Windows con PowerShell y Python. **No ejecutar comandos en EC2**.
- No modificar código, parámetros, tamaño de posición, órdenes ni procesos del bot sin autorización explícita.
- No cambiar el tamaño de las apuestas.
- No afirmar rentabilidad a partir del win rate. Hay pérdidas grandes y asimetría entre ganancias pequeñas y pérdidas completas.
- Separar operaciones reales, señales, eventos PAPER y rechazos.
- Un resultado PAPER no prueba que la entrada hubiera sido ejecutable al precio anotado.
- Las actualizaciones de cotización `pm/cambio` no son operaciones ejecutadas. `pm/trade` sí son impresiones del mercado, pero no prueban que el bot hubiera obtenido ese fill.
- Un VWAP calculado desde un snapshot del libro es una estimación, no garantía de ejecución.
- Varias estrategias que actúan sobre el mismo slug/ciclo son observaciones correlacionadas. Reportar tanto filas/eventos como mercados únicos.
- Desconexiones, silencios y huecos de captura son datos faltantes, no evidencia de ausencia de actividad.
- Nunca usar un snapshot futuro para reconstruir el precio disponible al momento de una señal.
- No extrapolar conclusiones de un solo periodo ni ajustar umbrales y evaluar en la misma muestra sin reservar validación fuera de muestra.

## 3. Entorno local y archivos

Carpeta base:

```text
C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta
```

Carpeta de extracción del microscopio:

```text
C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta\resultado_analisis_5m
```

Exportación de Telegram:

```text
C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta\result.json
```

CSV de ciclos PTB extraído de Telegram:

```text
C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta\ptb_ciclos_telegram.csv
```

Los archivos comprimidos del microscopio son enormes. No pedir que se adjunten completos: usar scripts locales y producir CSV/resúmenes compactos.

## 4. Datos disponibles

### 4.1 Microscopio de mercado

Se procesaron **59 archivos cronológicos** `microscopio_YYYYMMDD_HHMM.jsonl.gz`. El extractor excluyó el archivo parcial de las 21:00 y un archivo especial de ciclo que no pertenecía a la secuencia cronológica.

Resultado de extracción:

- 268,952,851 registros JSON válidos.
- 0 errores de JSON.
- 354 mercados 5m identificados.
- 347 resultados `meta/resultado`.
- 2,462 eventos de desconexión/silencio.
- 1,059,901 registros `pm/book`.
- 1,455,941 registros `pm/bba`.
- 528,089 registros `pm/trade`.
- Dos ciclos sin book, bba ni trade; otros dos ciclos muy escasos.
- Hay 14 ciclos faltantes dentro de la línea temporal: un hueco de 55 minutos (10 ciclos) y uno de 25 minutos (4 ciclos).

Ventana aproximada: 29-oct-2026 14:30 a 30-oct-2026 21:00 hora local de Nayarit (UTC-7). Para filtrar logs se usó el rango epoch **1793309100 a 1793419200**.

Archivos principales en `resultado_analisis_5m`:

- `pm_book_5m.jsonl`: snapshots de libro, timeframe 5m.
- `pm_bba_5m.jsonl`: mejor bid/ask.
- `pm_trade_5m.jsonl`: operaciones impresas.
- `btc_rtds_por_segundo.csv`: muestras RTDS reducidas por segundo y fuente.
- `resultados_meta.csv`: resultado ganador por ciclo.
- `conteo_fuentes.csv`, `conteo_ciclos_5m.csv`, `00_resumen_general.json`: resúmenes.

Estructura general de cada evento: claves superiores `t`, `s`, `e`, `d`.

- `t`: tiempo de recepción del colector; usar para alineación causal.
- `tx`: timestamp de origen con unidades/formatos mixtos; no mezclar sin normalizar.
- `d.m`: metadatos de mercado, normalmente `["5m", epoch, "UP" o "DN"]`. Filtrar estrictamente `d.m[0] == "5m"`.
- `d.v`: valor escalar para algunas fuentes RTDS.
- `meta/resultado`: ganador y datos de cierre.
- `meta/error_conexion` y `meta/silencio`: censura o huecos.

Para reconstrucción de libro: elegir el último snapshot con `t <= timestamp_evento`, mismo epoch y timeframe 5m. En `asks`/ `bids`, cada nivel es `[precio, cantidad]`. Caminar los asks para estimar VWAP al tamaño de referencia. Nunca usar el snapshot más cercano si es posterior al evento.

### 4.2 Logs de estrategias

Repositorio GitHub: `josuemtz1088-sys/chatgpt`, rama `main`.

- [tw_log.jsonl](https://raw.githubusercontent.com/josuemtz1088-sys/chatgpt/refs/heads/main/tw_log.jsonl)
- [flow_log.jsonl](https://raw.githubusercontent.com/josuemtz1088-sys/chatgpt/refs/heads/main/flow_log.jsonl)
- [cb_log.jsonl](https://raw.githubusercontent.com/josuemtz1088-sys/chatgpt/refs/heads/main/cb_log.jsonl)
- [resultados_meta.csv](https://raw.githubusercontent.com/josuemtz1088-sys/chatgpt/refs/heads/main/resultados_meta.csv)

Conteos completos:

- TW: 736 eventos.
- FLOW: 475 eventos.
- CB: 841 eventos.
- Total: 2,052 eventos.

Los logs se analizaron en la ventana común, pero no cubren todo el final de la ventana del microscopio:

- TW último evento aprox. 31-oct 01:06:41Z (30-oct 18:06:41 Nayarit), 2h53m antes del final del microscopio.
- FLOW último evento aprox. 30-oct 19:37:56Z (12:37:56 Nayarit), 8h22m antes.
- CB último evento aprox. 30-oct 21:17:13Z (14:17:13 Nayarit), 6h43m antes.

No concluir que no hubo señales en las horas no cubiertas por los logs.

### 4.3 Telegram y PTB

`result.json` es una exportación Telegram de aproximadamente 61.99 MB. Tiene un objeto superior con `messages`; cada mensaje incluye `id`, `date`, `date_unixtime`, `text`, `text_entities`, entre otros campos.

Mensajes relevantes:

- `Nuevo ciclo`: epoch del mercado, PTB inicial y BTC.
- `PTB watcher aplicado:`: corrección automática del watcher.
- `PTB actualizado a`: corrección manual.
- Algunas correcciones manuales son precedidas por un mensaje numérico enviado por el usuario.

El extractor local generó `ptb_ciclos_telegram.csv`:

- 77,218 mensajes Telegram.
- 37,463 ciclos extraídos.
- 368 ciclos esperados en la ventana.
- 358 encontrados.
- 10 faltantes.
- 36,924 ciclos con al menos una corrección.

Columnas del CSV: `epoch`, `fecha_inicio_mensaje`, `id_inicio`, `ptb_inicial`, `ptb_final`, `correcciones`, `ultima_correccion`, `id_ultima_correccion`.

## 5. Estrategias y filtros conocidos

Límites globales conocidos:

- `VOL_MAX = 4.0`
- `VOL60_MAX = 4.5`

Reglas documentadas:

**FLOW**
- `pm_net >= FLOW_PM_MIN` (valor conocido 2062)
- `cvd_bn60 >= FLOW_CVD_MIN` (2.529)
- `v60 < FLOW_V60_MAX`
- `sig >= FLOW_SIG_MIN` (1.9)
- `z >= FLOW_Z_MIN` (1.5)
- `ret_rel is None or ret_rel <= 0.10`

**CB**
- `cvd_cb30 < CB_CVD_MAX`
- Si z existe, `z >= CB_Z_MIN`.

**LATE**
- `elapsed >= LATE_FROM_SEC`
- `vel5 >= LATE_VEL5_MIN`
- `v10 >= LATE_V10_MIN`
- `v60 >= LATE_V60_MIN`
- `cb is None or cb < LATE_CB30_MAX`
- Rechaza si `vel5 < 2.0 and abs(cvd_cb30) < 0.10`.

**QUIET**
- `elapsed >= QUIET_FROM_SEC`
- `vel5 >= QUIET_VEL5_MIN`
- `pm60 < QUIET_PM60_MAX`
- PAPER-only salvo `QUIET_LIVE`.

Orden conocido de `_SideMethod.tick()`:

1. Regla de estrategia.
2. Post-loss guard para CB/FLOW.
3. Event pause.
4. Gate compartido `sig`: rechaza si `sig is None or sig >= VOL_MAX`.
5. Gate compartido `sig60`: rechaza si `sig60 is None or sig60 >= VOL60_MAX`.
6. Cushion, retorno/ret_rel, memoria, libro/precio/liquidez.

TW también usa los gates VOL_MAX y VOL60_MAX.

Rangos para clasificar sigma:

- <4: normal.
- 4 a <5: medio-alto.
- 5 a 6: alto.
- >6: extremo/fuera del objetivo.

**No subir VOL_MAX global por intuición:** afectaría a varias estrategias. Evaluar por estrategia/régimen y mantener las demás salvaguardas. Los umbrales alternativos comentados previamente fueron hipótesis sin validar; no implementarlos como si fueran resultados demostrados.

## 6. Hallazgos previos

### 6.1 Estadística global histórica (no limitada al periodo del microscopio)

Eventos:

- CB: 36 PAPER, 35 PAPER_RESULT, 109 RESULT, 122 SIGNAL, 173 SKIP_CUSH, 10 SKIP_EVENTO, 157 SKIP_PRICE, 94 SKIP_RET, 15 SKIP_RET_MEM, 72 SKIP_VOL, 18 SKIP_VOL60.
- FLOW: 46 PAPER, 45 PAPER_RESULT, 117 RESULT, 128 SIGNAL, 14 SKIP_CUSH, 4 SKIP_EVENTO, 67 SKIP_PRICE, 11 SKIP_RET, 1 RET_MEM, 33 SKIP_VOL, 9 SKIP_VOL60.
- TW: 138 SIGNAL, 133 RESULT, 21 SKIP_EVENTO, 85 SKIP_PRICE, 231 SKIP_VOL, 48 SKIP_VOL60.

Ledger histórico agregado reportado:

- 354 operaciones, 339W/15L.
- Win rate reportado 95.76%.
- PnL CSV +$111.89.
- Ganancias brutas +$650.26; pérdidas brutas -$538.37.
- Stake total $11,893.21.
- Ganancia media aproximada +$1.92; pérdida media aproximada -$35.89.

Este ledger no se ha reconciliado de manera independiente con fills, fees y settlements del exchange. No presentarlo como prueba definitiva de rentabilidad.

Por estrategia, ledger histórico:

- TW: 130 operaciones, 126W/4L, PnL -$2.13.
- FLOW: 117 operaciones, 112W/5L, PnL +$46.56.
- CB: 107 operaciones, 101W/6L, PnL +$67.46.

### 6.2 Ventana común con microscopio

- 505 eventos de logs en la ventana.
- 28 filas de resultados reales: 25 ganadas, 3 perdidas.
- Esos 28 resultados corresponden a 21 mercados únicos; no son 28 mercados independientes.
- Las tres pérdidas son el mismo mercado `btc-updown-5m-1793345400`, las tres en UP:
  - TW: precio 0.97, pérdida $51.94.
  - FLOW: precio 0.97, pérdida $20.37.
  - CB: precio 0.98, pérdida $7.84.
  - Pérdida conjunta: $80.15.
- En ese ciclo los libros eran frescos y la profundidad top-3 alta; no hay evidencia clara de libro obsoleto/delgado.
- Los 22 eventos PAPER de la ventana acertaron direccionalmente según meta, pero no prueban fills ni PnL ejecutable.

## 7. Foco inmediato: los 144 SKIP_VOL con sigma 4–6

Dentro de la ventana:

- 302 eventos `SKIP_VOL`; sigma disponible en 300.
- Distribución de `SKIP_VOL`: 90 entre 4–5; 54 entre 5–6; 156 >6; 2 sin sigma.
- Hay además 56 `SKIP_VOL60`: 27 en 4–5, 17 en 5–6, 12 >6. **No mezclar estos 56 con los 144 SKIP_VOL principales**; es otro gate.

Desglose de los 144:

| Banda sigma | TW | FLOW | CB | Eventos | Mercados únicos |
|---|---:|---:|---:|---:|---:|
| 4–5 | 57 | 15 | 18 | 90 | 81 |
| 5–6 | 37 | 5 | 12 | 54 | 50 |
| Total | 94 | 20 | 30 | 144 | 131 |

TW_SKIP_VOL no contiene `side`: los 94 TW requieren recuperar UP/DN. FLOW y CB sí guardan side en sus eventos SKIP_VOL.

Entre FLOW y CB con side explícito y resultado meta disponible:

- Sigma 4–5: 30 aciertos de 31 verificables; dos eventos sin resultado meta.
- Sigma 5–6: 17/17 aciertos.
- Esto no incluye TW y no representa el resultado final de los 144.

Hay duplicados por slug: varias estrategias pueden rechazar el mismo mercado. Presentar conteo por eventos y por mercados únicos.

## 8. Recuperación de dirección TW mediante PTB

Hipótesis de trabajo solicitada:

Para un mercado con epoch E, comparar el PTB final del ciclo E con el PTB final del siguiente ciclo E+300:

- Si PTB(E+300) > PTB(E): inferencia UP.
- Si PTB(E+300) < PTB(E): inferencia DN.
- Si son iguales, falta alguno o la asignación es ambigua: indeterminado.

Después comparar la inferencia con `ganador` de `resultados_meta.csv`.

**Importante:** esta regla debe validarse con la semántica exacta del PTB que usa el bot y con el settlement de Polymarket. No asumir que cualquier precio BTC de Telegram es automáticamente el mismo índice/fuente que resuelve el mercado.

### 8.1 Problema detectado en las correcciones Telegram

Se inspeccionaron 12 mensajes de corrección. Los mensajes no contienen `reply_to_message_id` (campo REPLY=None). Por tanto, no existe vínculo explícito en la exportación y no se deben asignar correcciones únicamente por cercanía temporal.

Hay dos clases de corrección:

- `PTB watcher aplicado: $X (diff=... vs calculado $Y)`: automática.
- `PTB actualizado a $X (diff=... vs calculado $Y)`: manual.

La cadena `vs calculado $Y` permite comparar con los anuncios y reconstruir candidatos de corrección. Se debe conservar el historial completo de anuncios/correcciones por epoch, no solo un valor agregado.

### 8.2 Muestras del CSV y alerta de duplicidad

Salida revisada del CSV:

| epoch | inicio CSV | PTB inicial | PTB final | correcciones |
|---|---|---:|---:|---:|
| 1793313300 | 2026-10-29 15:38:39 | 79067.40 | 78900.06 | 1 |
| 1793317500 | 2026-10-29 16:46:54 | 77883.04 | 78226.22 | 1 |
| 1793345400 | 2026-10-30 00:29:59 | 78329.75 | 78325.12 | 1 |
| 1793418600 | 2026-10-30 20:49:58 | 77076.16 | 77080.81 | 1 |

**Aclaración del usuario:** el cambio observado en epoch 1793313300 corresponde a un **reinicio del bot**, no a una anomalía de datos. El PTB $78,956.83 del mensaje id 142694 corresponde al ciclo previo a ese reinicio; el nuevo anuncio de ciclo (id 142695) con PTB $79,067.40 es el punto de partida posterior al reinicio, y la actualización manual a $78,900.06 (id 142697) es la corrección asociada a esa nueva sesión. Por tanto, el CSV no debe marcar este caso como anomalía. La auditoría debe reconocer explícitamente los reinicios/sesiones del bot y usar el PTB del ciclo vigente después del reinicio.

Ciclos faltantes en la ventana:

- 1793314800
- 1793315100
- 1793315400
- 1793315700
- 1793316000
- 1793316300
- 1793316600
- 1793316900
- 1793317200
- 1793392500

No interpolar PTB para ciclos faltantes.

## 9. Procedimiento técnico para cerrar la reconstrucción PTB

1. Leer `result.json` como JSON completo (objeto con arreglo `messages`, no JSONL).
2. Convertir `text` a texto plano preservando orden cuando sea string o arreglo de entidades.
3. Identificar **todos** los mensajes “Nuevo ciclo”; extraer epoch, PTB y fecha/id. Conservar duplicados, no sobrescribirlos silenciosamente.
4. Identificar mensajes “PTB watcher aplicado” y “PTB actualizado a”; extraer valor aplicado, valor calculado anterior, diff, timestamp e id.
5. Capturar también mensajes numéricos inmediatamente anteriores a correcciones manuales.
6. Vincular candidatos usando el importe `vs calculado`, valores de anuncios, orden cronológico y contexto. No usar solo proximidad temporal. Si hay más de una asociación posible, marcar ambigua.
7. Determinar qué PTB terminó usando realmente el bot para cada ciclo. Documentar evidencia y nivel de confianza.
8. Generar tabla de auditoría con epoch, anuncios originales, correcciones, PTB final seleccionado, motivo, confianza y estado (validado/ambiguo/faltante).
9. Para cada TW_SKIP_VOL, comparar E con E+300 usando únicamente PTB validados.
10. Comparar dirección inferida con ganador oficial en `resultados_meta.csv`.
11. Para FLOW/CB, conservar el side explícito y contrastarlo con meta; PTB puede servir como control adicional.
12. Reportar aciertos, fallos e indeterminados por estrategia, banda sigma, evento y mercado único.

## 10. Reconstrucción posterior de precio y ejecutabilidad

Una vez resuelta la dirección:

- Localizar en `pm_book_5m.jsonl` el último snapshot anterior o igual al timestamp del evento, mismo epoch, timeframe 5m y lado correcto.
- Registrar edad del snapshot, best ask, spread y profundidad.
- Calcular VWAP caminando los asks para el importe real registrado si existe.
- Para rechazos sin stake registrado, usar escalones comparables (p. ej. $5, $10, $20) y etiquetarlos como escenarios, no como apuestas reales.
- Cruzar `pm_bba_5m.jsonl` para validar best bid/ask.
- Usar `pm_trade_5m.jsonl` como contexto de prints, no como prueba de fill del bot.
- Cuantificar payout bruto posible según precio de entrada, pérdida potencial, spread y fees cuando se conozcan.
- Si no hay snapshot previo, marcar no reconstruible. No sustituir con el siguiente snapshot.
- Un rechazo solo puede recibir evaluación contrafactual si se puede reconstruir señal/dirección y el precio disponible antes del evento.

## 11. Otros filtros y líneas de análisis

Mantener separadas estas poblaciones:

- SKIP_VOL.
- SKIP_VOL60.
- SKIP_PRICE.
- SKIP_RET.
- SKIP_RET_MEM.
- SKIP_CUSH.
- SKIP_EVENTO.
- PAPER.
- Señales reales/resultados.

Comparar estrategias y poblaciones por sigma, precio, elapsed, z, CVD, PM net, v60, ret_rel, spread, profundidad y edad del libro. Analizar concentración de pérdidas en contratos caros (0.90+) y exposición combinada de estrategias en un mismo slug.

No crear umbrales nuevos con muestras pequeñas. Cualquier hipótesis de filtro debe probarse en periodo separado fuera de muestra.

## 12. Caso de estudio: mercado 1793345400

En `btc-updown-5m-1793345400`, TW, FLOW y CB entraron UP y perdieron:

- CB: epoch 1793345528.46, UP a 0.98, $7.84.
- FLOW: epoch 1793345501.22, UP a 0.97, $20.37.
- TW: epoch 1793345500.61, UP a 0.97, $51.94.
- Pérdida conjunta: $80.15.

Los libros estaban frescos (lags aprox. 0.016s, 0.032s y 0.272s) y profundidad top-3 aproximada de $10,229.93, $12,981.90 y $13,635.76. Sigma aprox. 2.6114; sigma60 aprox. 3.263–3.544; z aprox. 2.88–2.94. No parece un caso obvio de volatilidad excesiva ni de libro ralo. La compra a 0.97–0.98 dejó muy poco upside frente al riesgo de pérdida total.

El microscopio no tenía resultado meta para este ciclo; los logs de estrategia registran ganador DN. Confirmar con la fuente de resultados y documentar cualquier discrepancia.

## 13. Qué hacer al abrir una nueva conversación

Pegar este documento y escribir:

> Continuemos la auditoría desde el apartado 8. Tengo localmente result.json y ptb_ciclos_telegram.csv. Necesito auditar los anuncios duplicados y las correcciones PTB por epoch, validar la comparación E vs E+300 contra resultados_meta.csv y recuperar la dirección de los 94 eventos TW_SKIP_VOL. Trabajemos exclusivamente con PowerShell/Python local; no tocar EC2 ni el bot. Después evaluaremos los 144 rechazos por dirección, precio y liquidez.

Si la nueva conversación no tiene el contexto de GitHub, volver a consultar los cuatro archivos enlazados en el apartado 4.2. No es necesario volver a procesar los 59 gzip si la carpeta `resultado_analisis_5m` sigue intacta.

## 14. Definiciones del reporte final

- **Acierto direccional:** side registrado/inferido coincide con ganador oficial.
- **Fallo direccional:** side registrado/inferido difiere del ganador oficial.
- **No verificable:** falta PTB, falta resultado, hay ambigüedad, empate o calidad de datos insuficiente.
- **Evento:** una fila de señal/rechazo de una estrategia.
- **Mercado único:** un slug `btc-updown-5m-epoch`, aunque varias estrategias actúen en él.
- **Ejecutable estimado:** precio/profundidad derivados del libro disponible antes del evento; no es fill confirmado.
- **PAPER:** simulación o registro hipotético; no equivale a beneficio realizable.

---


## 15. Ajuste QUIET-UP — 2026-11-01

**Alcance:** modificación exclusiva de la regla `_rule_quiet(ctx)`. No modifica FLOW, CB, LATE, TW, filtros globales ni tamaños de posición.

**Evidencia retrospectiva usada:** 51 operaciones QUIET PAPER (49 ganadas, 2 perdidas). En el subconjunto UP hubo 26 señales: 24 ganadas y 2 perdidas. La combinación `cvd_cb30 > 0.543 AND ret_rel < 0.005` bloqueaba las dos pérdidas UP sin bloquear victorias UP en esa muestra. Aplicada globalmente habría bloqueado además tres victorias DN; por eso se limita a UP.

**Condición añadida:**
- Solo cuando `side == "UP"`.
- Bloquea si `cvd_cb30` está disponible y es estrictamente mayor que `0.543`.
- Y `ret_rel` está disponible y es estrictamente menor que `0.005`.
- Es una condición AND: ambas deben cumplirse.
- DN no se filtra por esta condición.
- Si falta cualquiera de las métricas, este filtro adicional no bloquea.

**Modo de operación:** QUIET permanece PAPER. `QUIET_LIVE=0` por defecto; no se habilita compra real. No cambiar ningún parámetro `*_PCT`.

**Estado de despliegue:** el cambio fue preparado en el archivo de GitHub `mr_bot_v4 1.0.2.py`. La aplicación al archivo local `mr_bot_v4.py` en EC2 requiere parche puntual, validación y reinicio autorizado. La actualización de GitHub por sí sola no cambia el proceso que ya está ejecutándose. Registrar por separado la fecha/hora de aplicación local y reinicio cuando se confirmen; no asumir que ya ocurrieron.

**Seguimiento:** conservar las 51 operaciones originales como línea base. Medir por separado señales QUIET-UP bloqueadas por esta condición, señales QUIET-UP que pasan, resultados PAPER y resultados DN. No mezclar esta evaluación con el análisis de LATE.


---

**Fin del documento de continuidad.**