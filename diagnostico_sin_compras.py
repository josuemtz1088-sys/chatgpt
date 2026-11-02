#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostico_sin_compras.py
Resume, de forma compacta, por qué el bot no compra. Corre LOCAL en Windows (no toca EC2 ni el bot).

Uso (PowerShell):
  python diagnostico_sin_compras.py --logs "C:\\ruta\\logs_1102_completo.tar.gz" --since "2026-11-01T19:00:00Z"

  --logs   : el .tar.gz descargado de EC2, o una carpeta ya extraída
  --since  : desde cuándo analizar (UTC, ISO). Pon la hora a la que reiniciaste el bot con la 1.0.3.
             Nayarit = UTC-7  (ej. 12:00 p. m. Nayarit = 19:00Z)
Salida: texto en pantalla + diagnostico_resumen.txt junto al script.
"""
import argparse, json, os, sys, tarfile, re
from collections import Counter, defaultdict
from datetime import datetime, timezone

def parse_since(s):
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()

def regimen(sig):
    if sig is None: return "sin_sigma"
    try: s = float(sig)
    except Exception: return "sin_sigma"
    if s < 4.0: return "normal(<4)"
    if s < 5.5: return "media(4-5.5)"
    if s < 7.0: return "alta(5.5-7)"
    return "extrema(>=7)"

def hora_local(ts):
    # Nayarit UTC-7
    return datetime.fromtimestamp(ts - 7 * 3600, tz=timezone.utc).strftime("%m-%d %H:00")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True)
    ap.add_argument("--since", required=True)
    a = ap.parse_args()
    since = parse_since(a.since)

    base = a.logs
    if os.path.isfile(base) and base.endswith((".tar.gz", ".tgz")):
        dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_extraidos")
        os.makedirs(dest, exist_ok=True)
        with tarfile.open(base, "r:gz") as t:
            t.extractall(dest)
        base = dest
        print(f"Extraído en: {dest}")

    out = []
    def P(x=""):
        print(x); out.append(x)

    jsonls, states, texts = [], [], []
    for root, _, files in os.walk(base):
        for f in files:
            p = os.path.join(root, f)
            if f.endswith(".jsonl"): jsonls.append(p)
            elif f.endswith("_state.json") or f.startswith("sizing_state"): states.append(p)
            elif f.endswith((".txt", ".log")): texts.append(p)

    P("=" * 70)
    P(f"Desde (UTC): {datetime.fromtimestamp(since, tz=timezone.utc)}")
    P(f"jsonl encontrados: {len(jsonls)} | state.json: {len(states)} | texto/log: {len(texts)}")

    # 1) Estado: estrategias apagadas tras pérdida
    P("\n[1] ESTADO GUARDADO (¿alguna estrategia quedó 'disabled' = solo papel?)")
    for p in states:
        try:
            d = json.load(open(p, encoding="utf-8"))
            P(f"  {os.path.basename(p)}: disabled={d.get('disabled')} wins={d.get('wins')} "
              f"losses={d.get('losses')} day={d.get('day')} count_day={d.get('count_day')} "
              f"paused_by_telegram={d.get('paused_by_telegram')}")
        except Exception as e:
            P(f"  {os.path.basename(p)}: no legible ({e})")
    if not states:
        P("  (no hay *_state.json en el tar; revisa en EC2 con ls, o dime los nombres)")

    # 2) Conteo de eventos por kind
    P("\n[2] EVENTOS POR TIPO (desde --since)")
    sig_por_slug = {}          # slug -> sigma (únicos por mercado)
    guard = Counter()          # (strategy, reason, missing)
    por_hora_sigma = defaultdict(Counter)
    for p in jsonls:
        name = os.path.basename(p)
        if name.startswith(("dataflow", "microscopio")):
            continue
        kinds = Counter()
        n = 0
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line: continue
                    try: r = json.loads(line)
                    except Exception: continue
                    ts = r.get("ts")
                    if ts is None or ts < since: continue
                    n += 1
                    k = r.get("kind") or r.get("decision") or "?"
                    if k == "NOT_EXECUTED": k = "NOT_EXECUTED:" + str(r.get("exec_status"))
                    kinds[k] += 1
                    if k == "POST_LOSS_GUARD" or k.endswith("_POST_LOSS_BLOCK"):
                        guard[(r.get("strategy"), r.get("reason"), ",".join(r.get("missing") or []), bool(r.get("blocked")))] += 1
                    sg = r.get("sigma")
                    slug = r.get("slug")
                    if sg is not None and slug and slug not in sig_por_slug:
                        sig_por_slug[slug] = (ts, sg)
        except Exception as e:
            P(f"  {name}: error leyendo ({e})")
            continue
        P(f"  --- {name}: {n} eventos")
        for k, v in kinds.most_common(25):
            P(f"      {k}: {v}")

    # 3) Guard post-pérdida
    P("\n[3] POST_LOSS_GUARD  (strategy, reason, datos faltantes, bloqueó)")
    if guard:
        for (s, rsn, miss, blk), v in guard.most_common(20):
            P(f"  {s} | {rsn} | missing=[{miss}] | blocked={blk}: {v}")
    else:
        P("  (sin registros del guard: o no corrió, o el archivo no está en el tar)")

    # 4) Régimen de σ por hora (mercados únicos con σ registrada)
    P("\n[4] RÉGIMEN DE VOLATILIDAD (σ de 15 min) por hora local Nayarit, mercados únicos")
    for slug, (ts, sg) in sig_por_slug.items():
        por_hora_sigma[hora_local(ts)][regimen(sg)] += 1
    for h in sorted(por_hora_sigma):
        P(f"  {h}: " + ", ".join(f"{k}={v}" for k, v in sorted(por_hora_sigma[h].items())))
    if not por_hora_sigma:
        P("  (ningún evento trae σ en la ventana)")

    # 5) Texto de consola: líneas clave
    P("\n[5] CONSOLA: líneas clave (conteo)")
    pats = {
        "APAGADO tras pérdida": r"APAGADO",
        "BUY no ejecutada": r"BUY no ejecutada",
        "EN PAPEL (no compra)": r"EN PAPEL",
        "WON": r" WON ",
        "LOST": r" LOST ",
        "error ignorado": r"error \(ignorado\)",
        "Traceback": r"Traceback",
        "RTDS desconectado": r"RTDS desconectado",
        "Binance WS error": r"Binance WS error",
        "451/403/geo": r"\b451\b|restricted|geo",
    }
    cnt = Counter()
    muestras = defaultdict(list)
    for p in texts:
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    for nm, rg in pats.items():
                        if re.search(rg, line):
                            cnt[nm] += 1
                            if len(muestras[nm]) < 2: muestras[nm].append(line.strip()[:160])
        except Exception:
            pass
    for nm in pats:
        P(f"  {nm}: {cnt.get(nm, 0)}")
        for m in muestras.get(nm, []):
            P(f"      ej: {m}")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnostico_resumen.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    P("\nListo. Pégame el contenido de diagnostico_resumen.txt (es corto).")

if __name__ == "__main__":
    main()