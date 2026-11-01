import sys, os, json, gzip, tarfile, re
from pathlib import Path
from collections import defaultdict

root = Path(sys.argv[1])
hist = Path(sys.argv[2])
out = Path(sys.argv[3])

TARGETS = [
    {
        "name": "CB",
        "epoch": "1793534700",
        "file": "microscopio_20261101_0500.jsonl.gz",
        "entry": 189.6
    },
    {
        "name": "FLOW",
        "epoch": "1793542500",
        "file": "microscopio_20261101_0700.jsonl.gz",
        "entry": 125.2
    }
]

ARCHIVES = [
    "logs_1031_1824.tar.gz",
    "logs_1031_2233.tar.gz",
    "logs_1101_0245.tar.gz",
    "logs_1101_1444.tar.gz"
]

def get_slug(d):
    for k in ("slug", "market_slug", "market", "condition_slug"):
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return ""

def get_elapsed(d, epoch):
    for k in ("elapsed", "elapsed_sec", "elapsed_seconds",
              "market_elapsed", "seconds_since_start", "t"):
        v = d.get(k)
        try:
            n = float(v)
            if abs(n) < 100000:
                return n
        except (TypeError, ValueError):
            pass

    for k in ("ts", "timestamp", "time"):
        try:
            n = float(d.get(k))
            if n > 1000000000:
                return n - float(epoch)
        except (TypeError, ValueError):
            pass
    return None

def compact(d):
    keep = {}
    pattern = re.compile(
        r"(price|ask|bid|mid|btc|spot|ptb|delta|sigma|zscore|"
        r"cvd|imbalance|velocity|vel|momentum|ret_rel|"
        r"volume|liquidity|spread|side|signal|entry|"
        r"chainlink|coinbase|binance|pm_net|pm60|v60|"
        r"age|regime|prob|score|fair|book|winner)",
        re.I
    )
    for k, v in d.items():
        if pattern.search(str(k)):
            if isinstance(v, (str, int, float, bool)) or v is None:
                keep[k] = v
    return keep if keep else d

report = []
report.append("DIAGNOSTICO SELECTIVO DE PERDIDAS")
report.append("=" * 75)
report.append("Microscopios: solo los dos archivos indicados.")
report.append("Historicos: cuatro archivos TAR indicados.")
report.append("")

# ---------------------------------------------------------
# 1. MICROSCOPE DATA FOR THE TWO RECENT LOSSES
# ---------------------------------------------------------
report.append("=" * 75)
report.append("1. RECONSTRUCCION SEGUNDO A SEGUNDO")
report.append("=" * 75)

for target in TARGETS:
    name = target["name"]
    epoch = target["epoch"]
    entry = target["entry"]
    path = root / target["file"]

    report.append("")
    report.append(f"--- {name} | ciclo {epoch} | entrada t+{entry}s ---")
    report.append(f"Archivo: {path.name}")

    if not path.exists():
        report.append("ERROR: no se encontro el archivo.")
        continue

    found = []
    matched = 0
    bad_json = 0

    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                if epoch not in line:
                    # También acepta el slug completo si el epoch no está literal.
                    slug = "btc-updown-5m-" + epoch
                    if slug not in line:
                        continue

                try:
                    d = json.loads(line)
                except Exception:
                    bad_json += 1
                    continue

                if not isinstance(d, dict):
                    continue

                matched += 1
                elapsed = get_elapsed(d, epoch)

                # Si no hay elapsed, se conserva el registro para inspección.
                if elapsed is None or entry - 60 <= elapsed <= entry + 10:
                    found.append((elapsed, line_no, compact(d)))

        report.append(f"Lineas coincidentes: {matched}")
        report.append(f"Lineas JSON invalidas: {bad_json}")
        report.append(f"Registros en ventana: {len(found)}")

        found.sort(key=lambda x: (
            x[0] is None,
            x[0] if x[0] is not None else 0
        ))

        for elapsed, line_no, data in found:
            t = "SIN_TIEMPO" if elapsed is None else f"t+{elapsed:.2f}s"
            report.append(f"{t} | linea {line_no} | {json.dumps(data, ensure_ascii=False)}")

        if not found:
            report.append("No se encontraron registros coincidentes por epoch/slug.")
            report.append("Revisar si el microscopio usa otro identificador de mercado.")

    except Exception as e:
        report.append(f"ERROR leyendo microscopio: {repr(e)}")

# ---------------------------------------------------------
# 2. HISTORICAL EXECUTED LOSSES
# ---------------------------------------------------------
report.append("")
report.append("=" * 75)
report.append("2. PERDIDAS HISTORICAS CON SEÑAL Y RESULTADO")
report.append("=" * 75)

for archive_name in ARCHIVES:
    archive_path = hist / archive_name
    report.append("")
    report.append(f"--- ARCHIVO {archive_name} ---")

    if not archive_path.exists():
        report.append("NO ENCONTRADO")
        continue

    signals = defaultdict(list)
    results = defaultdict(list)
    members_read = 0
    json_errors = 0

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile() or not member.name.endswith(".jsonl"):
                    continue

                base = Path(member.name).name.lower()
                if not any(x in base for x in
                           ("cb_log", "flow_log", "tw_log", "late_log", "quiet_log")):
                    continue

                prefix = base.split("_")[0].upper()
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue

                members_read += 1
                for raw in extracted:
                    try:
                        d = json.loads(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        json_errors += 1
                        continue

                    if not isinstance(d, dict):
                        continue

                    kind = str(d.get("kind", "")).upper()
                    slug = get_slug(d)
                    if not slug:
                        continue

                    if kind.endswith("_SIGNAL"):
                        signals[(prefix, slug)].append(d)
                    elif kind.endswith("_RESULT"):
                        results[(prefix, slug)].append(d)

        losses = []
        for key, result_list in results.items():
            pfx, slug = key
            for result in result_list:
                won = result.get("won")
                if won is not False:
                    continue

                candidates = signals.get(key, [])
                # Preferimos la señal ejecutada (ok=true y fill_price presente).
                executed = []
                for s in candidates:
                    ok = s.get("ok")
                    fill = s.get("fill_price", s.get("entry_price"))
                    if ok is True and fill is not None:
                        executed.append(s)

                signal = executed[-1] if executed else (
                    candidates[-1] if candidates else {}
                )

                losses.append((pfx, slug, signal, result, bool(executed)))

        report.append(f"Logs leidos: {members_read} | errores JSON: {json_errors}")
        report.append(f"Resultados perdedores encontrados: {len(losses)}")

        for pfx, slug, signal, result, executed in losses:
            report.append("")
            report.append(
                f"{pfx} | {slug} | EJECUTADA={executed}"
            )
            report.append("SEÑAL: " + json.dumps(compact(signal), ensure_ascii=False))
            report.append("RESULTADO: " + json.dumps(compact(result), ensure_ascii=False))

    except Exception as e:
        report.append(f"ERROR leyendo TAR: {repr(e)}")

report.append("")
report.append("=" * 75)
report.append("FIN DEL DIAGNOSTICO")
report.append("=" * 75)

out.write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
print(f"\nREPORTE GUARDADO EN: {out}")
