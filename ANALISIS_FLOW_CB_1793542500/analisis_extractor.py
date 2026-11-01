import os, sys, json, gzip, tarfile, zipfile, re
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])

TARGETS = {"1793534700", "1793542500"}
METHODS = ("CB", "FLOW", "TW", "LATE", "QUIET")
KEYWORDS = (
    "signal", "entry", "buy", "filled", "settle", "result",
    "win", "loss", "trade", "execute", "skip", "blocked",
    "order", "position", "close", "reject", "guard"
)

def json_load(line):
    try:
        return json.loads(line)
    except Exception:
        return None

def walk(obj, depth=0):
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower(), v
            yield from walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:100]:
            yield from walk(v, depth + 1)

def values(obj):
    for _, v in walk(obj):
        if isinstance(v, (str, int, float)):
            yield str(v)

def has_target(obj):
    return any(t in v for v in values(obj) for t in TARGETS)

def get_kind(obj):
    for k, v in walk(obj):
        if k in ("kind", "event", "type", "event_type", "action") and isinstance(v, str):
            return v[:100]
    return "UNKNOWN"

def get_method(obj):
    for k, v in walk(obj):
        if k in ("method", "strategy", "rule", "bot", "source", "signal_name"):
            if isinstance(v, str):
                u = v.upper()
                for m in METHODS:
                    if m in u:
                        return m
    text = " ".join(values(obj)).upper()
    for m in METHODS:
        if re.search(r"\b" + m + r"\b", text):
            return m
    return "UNKNOWN"

def event_candidate(obj):
    text = " ".join(values(obj)).lower()
    has_action = any(k in text for k in KEYWORDS)
    has_method = get_method(obj) != "UNKNOWN"
    has_market = any(x in text for x in ("slug", "market", "epoch", "cycle"))
    return has_action and has_method and has_market

def elapsed_values(obj):
    found = []
    for k, v in walk(obj):
        if k in ("elapsed", "elapsed_s", "elapsed_sec", "seconds_into",
                 "market_elapsed", "cycle_elapsed", "t", "t_sec"):
            try:
                n = float(v)
                if -5 <= n <= 600:
                    found.append((k, n))
            except Exception:
                pass
    return found

def write_jsonl(handle, source, line_no, obj):
    handle.write(json.dumps({
        "_source": source,
        "_line": line_no,
        "data": obj
    }, ensure_ascii=False) + "\n")

summary = []
kind_counts = Counter()
method_counts = Counter()
source_counts = Counter()
target_counts = Counter()
elapsed_hist = Counter()
samples = {}
invalid = Counter()
historical_count = 0
target_count = 0

target_file = OUT / "ciclos_perdedores.jsonl"
hist_file = OUT / "historico_senales_ejecuciones.jsonl"
schema_file = OUT / "muestras_estructura.jsonl"

# 1. DATAFLOW: recorrer completo, guardar ciclos objetivo y eventos históricos.
dataflow = ROOT / "dataflow_log.jsonl"
if dataflow.exists():
    print("1/4 Escaneando Dataflow (archivo grande)...")
    with open(dataflow, "r", encoding="utf-8", errors="replace") as fin, \
         open(target_file, "w", encoding="utf-8") as ft, \
         open(hist_file, "w", encoding="utf-8") as fh, \
         open(schema_file, "w", encoding="utf-8") as fs:

        for i, line in enumerate(fin, 1):
            obj = json_load(line)
            if obj is None:
                invalid["dataflow"] += 1
                continue

            kind = get_kind(obj)
            method = get_method(obj)
            kind_counts[kind] += 1

            if len(samples) < 30 and kind not in samples:
                samples[kind] = obj
                write_jsonl(fs, "dataflow", i, obj)

            if has_target(obj):
                write_jsonl(ft, "dataflow", i, obj)
                target_count += 1
                target_counts[kind] += 1

            if event_candidate(obj):
                write_jsonl(fh, "dataflow", i, obj)
                historical_count += 1
                method_counts[method] += 1
                source_counts["dataflow"] += 1
                for k, v in elapsed_values(obj):
                    bucket = int(v // 30) * 30
                    elapsed_hist[f"{bucket}-{bucket+29}s"] += 1

    summary.append(f"DATAFLOW: {dataflow.stat().st_size:,} bytes")
else:
    print("ADVERTENCIA: no existe dataflow_log.jsonl")

# 2. TAR: revisar archivos internos de logs y extraer eventos relevantes.
tar_path = ROOT / "logs_1101_1444.tar.gz"
tar_members = []

if tar_path.exists():
    print("2/4 Escaneando logs_1101_1444.tar.gz...")
    with tarfile.open(tar_path, "r:gz") as tar, \
         open(target_file, "a", encoding="utf-8") as ft, \
         open(hist_file, "a", encoding="utf-8") as fh, \
         open(schema_file, "a", encoding="utf-8") as fs:

        for member in tar:
            if not member.isfile():
                continue
            name = member.name
            if not name.lower().endswith((".jsonl", ".json", ".log", ".txt", ".csv")):
                continue

            tar_members.append(name)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue

            for i, raw in enumerate(extracted, 1):
                try:
                    line = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue
                if not line:
                    continue

                obj = json_load(line)
                if obj is None:
                    if any(t in line for t in TARGETS):
                        ft.write(json.dumps({
                            "_source": "tar:" + name,
                            "_line": i,
                            "raw": line[:20000]
                        }, ensure_ascii=False) + "\n")
                        target_count += 1
                    continue

                kind = get_kind(obj)
                method = get_method(obj)

                if has_target(obj):
                    write_jsonl(ft, "tar:" + name, i, obj)
                    target_count += 1
                    target_counts[kind] += 1

                if event_candidate(obj):
                    write_jsonl(fh, "tar:" + name, i, obj)
                    historical_count += 1
                    method_counts[method] += 1
                    source_counts["tar"] += 1
                    for k, v in elapsed_values(obj):
                        bucket = int(v // 30) * 30
                        elapsed_hist[f"{bucket}-{bucket+29}s"] += 1

    summary.append("TAR miembros revisados: " + str(len(tar_members)))
else:
    print("ADVERTENCIA: no existe logs_1101_1444.tar.gz")

# 3. MICROSCOPIOS: seleccionar ventanas próximas a los dos ciclos.
micros = sorted(ROOT.glob("microscopio_20261101_*.jsonl.gz"))
wanted_minutes = {430, 500, 530, 630, 700, 730, 800}
selected = []

for p in micros:
    match = re.search(r"_(\d{2})(\d{2})\.jsonl\.gz$", p.name)
    if match:
        minute = int(match.group(1)) * 60 + int(match.group(2))
        if minute in wanted_minutes:
            selected.append(p)

print("3/4 Microscopios seleccionados:", len(selected))

micro_target = OUT / "microscopios_ciclos_objetivo.jsonl"
micro_samples = OUT / "muestras_microscopios.jsonl"
micro_counts = Counter()

with open(micro_target, "w", encoding="utf-8") as fo, \
     open(micro_samples, "w", encoding="utf-8") as fs:

    for p in selected:
        print("  Leyendo", p.name)
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fin:
            for i, line in enumerate(fin, 1):
                obj = json_load(line)
                if obj is None:
                    invalid["micro:" + p.name] += 1
                    continue

                kind = get_kind(obj)
                if len(micro_counts) < 100:
                    micro_counts[kind] += 1

                if has_target(obj):
                    write_jsonl(fo, p.name, i, obj)
                    target_count += 1
                    target_counts["MICRO:" + kind] += 1

                # Muestras iniciales para conocer campos del microscopio.
                if i <= 3:
                    write_jsonl(fs, p.name, i, obj)

# 4. Código local del bot.
bot = ROOT / "mr_bot_v4.py"
if bot.exists():
    import shutil
    shutil.copy2(bot, OUT / "mr_bot_v4.py")

# Resumen.
summary_path = OUT / "RESUMEN.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("ANALISIS FLOW + CB | CICLOS 1793542500 Y 1793534700\n")
    f.write("=" * 65 + "\n\n")
    f.write("CICLOS OBJETIVO:\n")
    f.write("CB: 1793534700\nFLOW: 1793542500\n\n")
    f.write(f"Registros objetivo extraidos: {target_count}\n")
    f.write(f"Eventos historicos candidatos extraidos: {historical_count}\n")
    f.write(f"Microscopios seleccionados: {len(selected)}\n\n")

    f.write("ARCHIVOS MICROSCOPIO:\n")
    for p in selected:
        f.write(f"{p.name} | {p.stat().st_size:,} bytes\n")

    f.write("\nEVENTOS HISTORICOS POR METODO:\n")
    for k, v in method_counts.most_common():
        f.write(f"{k}: {v}\n")

    f.write("\nEVENTOS HISTORICOS POR FUENTE:\n")
    for k, v in source_counts.items():
        f.write(f"{k}: {v}\n")

    f.write("\nDISTRIBUCION DE ELAPSED DETECTADOS:\n")
    for k, v in sorted(elapsed_hist.items()):
        f.write(f"{k}: {v}\n")

    f.write("\nTIPOS EN CICLOS OBJETIVO:\n")
    for k, v in target_counts.most_common():
        f.write(f"{k}: {v}\n")

    f.write("\nMIEMBROS DEL TAR:\n")
    for x in tar_members:
        f.write(x + "\n")

    f.write("\nERRORES JSON:\n")
    for k, v in invalid.items():
        f.write(f"{k}: {v}\n")

    f.write("\nIMPORTANTE: los conteos de candidatos no son conteos de operaciones.")
    f.write("\nSe deben deduplicar por señal/orden/mercado antes de calcular win rate.")
    f.write("\nLa clasificacion de ganadores debe usar resultado final y fills reales.")

print("\n4/4 Generando paquete...")
if Path(str(OUT) + ".zip").exists():
    Path(str(OUT) + ".zip").unlink()

with zipfile.ZipFile(str(OUT) + ".zip", "w", zipfile.ZIP_DEFLATED, compresslevel=5) as z:
    for p in OUT.iterdir():
        if p.is_file() and p.name != "analisis_extractor.py":
            z.write(p, arcname=p.name)

print("\nTERMINADO")
print("Resumen:", summary_path)
print("Registros objetivo:", target_count)
print("Candidatos historicos:", historical_count)
print("Microscopios:", len(selected))
print("ZIP:", str(OUT) + ".zip")
