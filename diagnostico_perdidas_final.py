import sys, json, gzip, tarfile
from pathlib import Path
from collections import defaultdict

root, hist, out = map(Path, sys.argv[1:4])

targets = [
    ("CB", "1793534700", "microscopio_20261101_0500.jsonl.gz", 189.6),
    ("FLOW", "1793542500", "microscopio_20261101_0700.jsonl.gz", 125.2),
]

archives = [
    "logs_1031_1824.tar.gz",
    "logs_1031_2233.tar.gz",
    "logs_1101_0245.tar.gz",
    "logs_1101_1444.tar.gz",
]

def clean(value, key=""):
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            # Los libros se reducen a sus primeros niveles.
            if k in ("bids", "asks") and isinstance(v, list):
                result[k] = v[:5]
            else:
                result[k] = clean(v, k)
        return result

    if isinstance(value, list):
        return [clean(x) for x in value[:15]]

    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "...[recortado]"

    return value

def slug_of(d):
    for k in ("slug", "market_slug", "market"):
        if isinstance(d.get(k), str):
            return d[k]
    return ""

def compact(d):
    keys = (
        "kind", "slug", "ok", "won", "fill_price", "entry_price",
        "side", "direction", "amount", "size", "pnl_est", "pnl",
        "elapsed", "price", "rule", "reason", "signal", "winner",
        "ptb", "ds_delta", "ds_age", "v60", "pm_net_side_usd",
        "cvd_bn_60s_side", "cvd_cb_30s_side", "vel5", "ret_rel",
        "sigma", "sigma60", "z", "pm60_side_usd", "pct",
        "regime", "market"
    )
    return {k: clean(d[k], k) for k in keys if k in d}

lines = []
lines.append("DIAGNOSTICO FINAL SELECTIVO")
lines.append("=" * 80)
lines.append("Tiempo microscopio: t Unix absoluto.")
lines.append("Ventana: entrada -60 segundos hasta entrada +10 segundos.")
lines.append("")

# --------------------------------------------------
# 1. MICROSCOPE WINDOWS
# --------------------------------------------------
for name, epoch, filename, entry_elapsed in targets:
    path = root / filename
    epoch_n = float(epoch)
    entry_ts = epoch_n + entry_elapsed
    start_ts = entry_ts - 60
    end_ts = entry_ts + 10

    lines += [
        "",
        "=" * 80,
        f"MICROSCOPIO {name}",
        f"Mercado: btc-updown-5m-{epoch}",
        f"Entrada: t+{entry_elapsed}s | Unix {entry_ts:.3f}",
        f"Ventana Unix: {start_ts:.3f} a {end_ts:.3f}",
        f"Archivo: {filename}",
        "=" * 80,
    ]

    if not path.exists():
        lines.append("ERROR: archivo no encontrado")
        continue

    count = 0
    invalid = 0

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line_no, raw in enumerate(f, 1):
            try:
                obj = json.loads(raw)
            except Exception:
                invalid += 1
                continue

            if not isinstance(obj, dict):
                continue

            try:
                ts = float(obj["t"])
            except (KeyError, TypeError, ValueError):
                continue

            if ts < start_ts or ts > end_ts:
                continue

            source = obj.get("s", "?")
            event = obj.get("e", "?")
            data = obj.get("d", {})

            # Añadimos tiempo relativo al inicio del mercado.
            record = {
                "elapsed": round(ts - epoch_n, 3),
                "unix": round(ts, 3),
                "source": source,
                "event": event,
                "data": clean(data)
            }

            lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            count += 1

    lines.append(f"TOTAL REGISTROS EN VENTANA: {count}")
    lines.append(f"LINEAS JSON INVALIDAS: {invalid}")

# --------------------------------------------------
# 2. HISTORICAL LOSSES
# --------------------------------------------------
lines += ["", "=" * 80, "PERDIDAS HISTORICAS", "=" * 80]

for archive_name in archives:
    path = hist / archive_name
    lines += ["", f"ARCHIVO: {archive_name}"]

    if not path.exists():
        lines.append("NO ENCONTRADO")
        continue

    signals = defaultdict(list)
    results = defaultdict(list)
    read_logs = 0
    errors = 0

    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".jsonl"):
                continue

            base = Path(member.name).name.lower()
            if not any(x in base for x in
                       ("cb_log", "flow_log", "tw_log", "late_log", "quiet_log")):
                continue

            prefix = base.split("_")[0].upper()
            stream = tar.extractfile(member)
            if stream is None:
                continue

            read_logs += 1

            for raw in stream:
                try:
                    d = json.loads(raw.decode("utf-8", errors="replace"))
                except Exception:
                    errors += 1
                    continue

                if not isinstance(d, dict):
                    continue

                kind = str(d.get("kind", "")).upper()
                slug = slug_of(d)
                if not slug:
                    continue

                key = (prefix, slug)

                if kind.endswith("_SIGNAL"):
                    signals[key].append(d)
                elif kind.endswith("_RESULT"):
                    results[key].append(d)

    losses = []

    for key, result_list in results.items():
        prefix, slug = key

        for result in result_list:
            if result.get("won") is not False:
                continue

            candidates = signals.get(key, [])
            executed = [
                s for s in candidates
                if s.get("ok") is True
                and s.get("fill_price", s.get("entry_price")) is not None
            ]

            signal = executed[-1] if executed else (
                candidates[-1] if candidates else {}
            )

            losses.append((prefix, slug, signal, result, bool(executed)))

    lines.append(f"Logs leidos: {read_logs} | errores JSON: {errors}")
    lines.append(f"Perdidas encontradas: {len(losses)}")

    for prefix, slug, signal, result, executed in losses:
        lines.append("")
        lines.append(f"{prefix} | {slug} | EJECUTADA={executed}")
        lines.append("SIGNAL " + json.dumps(compact(signal), ensure_ascii=False))
        lines.append("RESULT " + json.dumps(compact(result), ensure_ascii=False))

lines += ["", "=" * 80, "FIN"]

out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[-30:]))
print(f"\nREPORTE GUARDADO: {out}")
print(f"TAMAÑO: {out.stat().st_size / 1024 / 1024:.2f} MB")
