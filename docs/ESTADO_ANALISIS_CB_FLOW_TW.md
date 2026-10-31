# Estado de trabajo — análisis CB / FLOW / TW por volatilidad

**Fecha de actualización:** 31 de octubre de 2026  
**Repositorio:** `josuemtz1088-sys/chatgpt`

## Objetivo

Analizar conjuntamente los métodos **CB, FLOW y TW** del bot BTC Up/Down de 5 minutos en Polymarket, usando los registros reales del microscopio y DataFlow, para determinar cómo deben comportarse en tres bandas de volatilidad:

- NORMAL
- ALTA
- MUY ALTA

La meta es mantener oportunidades de compra en las tres bandas, con filtros de entrada más selectivos en ALTA y MUY ALTA, proporcionales a la volatilidad y específicos para cada método. **No aumentar los importes de compra.**

## Restricciones que no deben perderse

1. En volatilidad NORMAL, conservar exactamente los parámetros actuales.
2. No imponer los mismos umbrales a CB, FLOW y TW: cada método tiene señales, métricas y comportamiento propios.
3. No modificar todavía el bot ni sus parámetros live. Primero terminar el análisis, validar la evidencia y presentar una propuesta.
4. Basar cortes y umbrales en distribuciones observadas; no inventar límites ni extrapolar muestras pequeñas.
5. Excluir por completo el ciclo `1793345400`. El usuario indicó expresamente que ya está cerrado y no debe reabrirse ni volver a analizarse.
6. Microscopio y DataFlow se ejecutan localmente en **Windows PowerShell**, no en AWS/EC2.
7. No confundir snapshots de balance con operaciones ni con PnL.
8. Un resultado `WON` debe tratarse como ganador cuando corresponda a la resolución real del mercado. No clasificarlo como pérdida por discrepancias de snapshots.
9. Separar señales, compras reales, paper/shadow y rechazos. PAPER y REJECT no son WIN/LOSS por sí mismos.

## Entorno y archivos identificados

Carpeta local de trabajo observada:

`C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta`

Archivos relevantes identificados:

- `dataflow_cruce_microscopio.csv` — aproximadamente 50 KB; cruce de DataFlow con microscopio.
- Múltiples archivos `microscopio_YYYYMMDD_HHMM.jsonl.gz`, con registros históricos comprimidos.
- `microscopio_ciclo_1793345400.jsonl.gz` — **excluir**.
- `analizar_volatilidad_3_metodos.py` — script local de análisis.
- `analizar_microscopios_5m.py`
- `inspeccionar_microscopios.py`
- `inspeccion_microscopios.txt`
- `operaciones_con_microscopio.py`

El script de análisis se ejecuta desde PowerShell con:

```powershell
Set-Location "C:\Users\Paul campos\Desktop\Nueva carpeta (3)\Nueva carpeta"
py .\analizar_volatilidad_3_metodos.py
```

No pegar sintaxis Linux (`cat <<'PY'`) en PowerShell. Para código Python, guardarlo en un archivo `.py` y ejecutarlo con `py archivo.py`.

## Estado técnico / precauciones de la ejecución

Se detectó que el patrón de entrada original del analizador podía incluir accidentalmente el archivo del ciclo excluido y no incluía `dataflow_cruce_microscopio.csv`. La corrección propuesta fue:

- Añadir `dataflow_cruce_microscopio.csv` a los patrones de entrada.
- Filtrar explícitamente `microscopio_ciclo_1793345400.jsonl.gz` por nombre.
- Antes de confiar en resultados, validar que los encabezados y filas del CSV coincidan con los campos que el analizador espera.

La ejecución completa de muchos JSONL.GZ puede tardar. No iniciar análisis duplicados innecesarios. Si hay que detener una ejecución, detener **solo el proceso del analizador**, nunca `microscopio.py` ni `dataflow_watcher.py`. PIDs vistos en una sesión anterior pueden cambiar; comprobar el proceso actual antes de actuar.

La versión inicial del analizador tiene riesgos metodológicos que deben revisarse antes de aceptar sus resultados: clasificación heurística de método/resultado, bandas de sigma no validadas, deduplicación simple y cruce incompleto con la resolución real del mercado. No considerar sus tasas como definitivas sin validar estructura, ground truth y duplicados.

## Corte histórico

Se había acordado analizar datos posteriores al miércoles 28 de octubre de 2026 a las 14:00, comenzando por el mercado `1793221200`, si la cobertura disponible lo permite. Mantener siempre excluido `1793345400`. Si el dataset no permite aplicar exactamente ese corte, documentar la cobertura real en vez de inventar fechas.

## Qué debe producir el análisis

### 1. Cobertura y calidad de datos
- Archivos incluidos y excluidos, rango temporal y cantidad de registros.
- Cobertura de CB, FLOW y TW por separado.
- Integridad del cruce con DataFlow y resolución de mercados.
- Duplicados, campos ausentes y limitaciones.

### 2. Resultados separados por método y banda
Para CB, FLOW y TW, y para NORMAL / ALTA / MUY ALTA:
- Número de señales.
- Compras reales.
- Operaciones paper/shadow.
- Rechazos, separados por razón.
- WIN/LOSS únicamente cuando exista resolución real verificable.
- Tasas con denominador explícito y tamaño de muestra.

### 3. Métricas que deben contrastarse
Cuando existan en los registros, comparar distribuciones de WIN y LOSS y de entradas/rechazos:
- Sigma/volatilidad y campo fuente usado por cada método.
- Range y range_pct.
- Velocidad a 15/30/60 segundos y aceleración.
- CVD 30/60 segundos y CVD de fuentes disponibles (perp, CB, Binance).
- Book imbalance, spread y liquidez top 3.
- CB premium, dominancia, streak y confirmaciones.
- Precio/ask y demás variables que realmente intervengan en cada método.

No asumir que todos los campos existen para todos los métodos. Registrar nombre exacto, fuente, unidades y cobertura.

### 4. Rechazos y oportunidades perdidas
- Cuantificar rechazos por método, banda y motivo.
- Cuando sea posible, cruzar cada rechazo con el movimiento posterior y la resolución del mercado.
- Distinguir rechazos que evitaron una pérdida de rechazos que descartaron una oportunidad ganadora.
- No llamar “bueno” o “malo” a un rechazo sin evidencia posterior suficiente.

### 5. Entrega final
Preparar una matriz de candidatos por método y banda:

| Método | NORMAL | ALTA | MUY ALTA |
|---|---|---|---|
| CB | Mantener configuración actual | Criterios candidatos sustentados | Criterios candidatos sustentados |
| FLOW | Mantener configuración actual | Criterios candidatos sustentados | Criterios candidatos sustentados |
| TW | Mantener configuración actual | Criterios candidatos sustentados | Criterios candidatos sustentados |

Para cada cambio candidato indicar: valor actual, valor observado/propuesto, muestra, evidencia, efecto esperado y trade-off. No aplicar cambios automáticamente. Mantener el tamaño de compra actual.

## Próximos pasos al retomar

1. Confirmar que la ejecución local terminó y conservar su salida; no detener microscopio ni DataFlow.
2. Revisar primero el reporte de cobertura (por ejemplo `analisis_volatilidad_3_metodos/00_cobertura.json`, si fue generado) y los CSV de salida.
3. Inspeccionar encabezados y muestras de `dataflow_cruce_microscopio.csv`; verificar que realmente se incorporó.
4. Auditar cómo el analizador identifica método, compra, rechazo, resultado y resolución. Corregir clasificación antes de calcular tasas.
5. Verificar exclusión total de `1793345400` en archivos de entrada y resultados.
6. Solo entonces calcular comparaciones y proponer criterios por método/banda. No tocar parámetros live.

## Regla de continuidad

Si se retoma este trabajo en otro chat, comenzar leyendo este documento y pedir al usuario únicamente la salida/estado actual del proceso local o los reportes que ya se hayan generado. No volver a empezar desde cero ni pedirle que repita los objetivos y restricciones anteriores.
