#!/usr/bin/env python3
"""Replay the captured sample days at 5-minute resolution (roadmap item 10b).

The hourly engine samples one offer book per hour (the HH:05 book). The sample
days archived by pipeline/archive_rtdoe.py keep the FULL per-5-minute books, so
this deriver clears each 5-minute interval's book against that grid's own
dispatched generation (RTDSUM) to a marginal price, giving a 288-point intraday
price series per grid that the hourly replay smooths away. It is the only public
5-minute WESM price replay anywhere, a deep-dive on the sample days, not a
window-wide engine.

Writes data/derived/rtdoe5_replay.json; build_data bakes it to
web/data/rtdoe5.json for the studio's 5-minute view.

    python3 pipeline/rtdoe5_replay.py --derive
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RTDOE5 = os.path.join(HERE, "..", "data", "derived", "rtdoe_5min")
RTDSUM = os.path.join(HERE, "..", "data", "raw", "RTDSUM")
OUT = os.path.join(HERE, "..", "data", "derived", "rtdoe5_replay.json")
REGION = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")
OFFER_CAP = 32.0  # sourced WESM offer cap PhP/kWh


def _norm(ts: str) -> str | None:
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None


def _generation(date: str) -> dict[str, dict[str, float]]:
    """{interval_key: {grid: dispatched generation MW}} from RTDSUM."""
    path = os.path.join(RTDSUM, f"RTDREG_{date.replace('-', '')}.csv")
    if not os.path.isfile(path):
        return {}
    out: dict[str, dict[str, float]] = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            key = _norm((r.get("TIME_INTERVAL") or "").strip())
            if not g or not key:
                continue
            try:
                gen = float(r.get("GENERATION") or 0)
            except ValueError:
                continue
            out.setdefault(key, {})[g] = gen
    return out


def _clear(blocks: list, demand: float) -> float:
    """Merit-order marginal price: fill the price-sorted book to demand and
    return the last block's price, the offer cap if the book is short."""
    filled = 0.0
    for price, mw in sorted(blocks, key=lambda b: b[0]):
        filled += mw
        if filled >= demand:
            return round(price, 3)
    return OFFER_CAP


def replay_day(date: str) -> dict | None:
    book_path = os.path.join(RTDOE5, f"RTDOE5_{date.replace('-', '')}.json")
    if not os.path.isfile(book_path):
        return None
    book = json.load(open(book_path))
    gen = _generation(date)
    keys = sorted(book["intervals"])
    series = {g: [] for g in GRIDS}
    labels = []
    for k in keys:
        labels.append(k[11:16])  # HH:MM
        iv = book["intervals"][k]
        for g in GRIDS:
            blocks = iv.get(g) or []
            demand = (gen.get(k) or {}).get(g, 0.0)
            series[g].append(_clear(blocks, demand) if blocks and demand > 0
                             else None)
    # hourly mean per grid, for the "what the hourly replay sees" overlay
    hourly = {g: [] for g in GRIDS}
    for g in GRIDS:
        for h in range(24):
            vals = [series[g][i] for i, lab in enumerate(labels)
                    if lab.startswith(f"{h:02d}:") and series[g][i] is not None]
            hourly[g].append(round(sum(vals) / len(vals), 3) if vals else None)
    n = sum(1 for v in series["luzon"] if v is not None)
    return {"date": date, "labels": labels, "series": series,
            "hourly": hourly, "n_priced": n}


def derive() -> dict:
    days = []
    for name in sorted(os.listdir(RTDOE5)):
        if not name.startswith("RTDOE5_") or not name.endswith(".json"):
            continue
        s = name[len("RTDOE5_"):-len(".json")]
        date = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        d = replay_day(date)
        if d and d["n_priced"] > 200:
            days.append(d)
    days.sort(key=lambda x: x["date"])
    return {
        "available": bool(days),
        "unit": "PhP/kWh",
        "days": days,
        "note": ("Each 5-minute interval's offer book (RTDOE) cleared to that "
                 "grid's own dispatched generation (RTDSUM) at merit order, the "
                 "intraday price volatility the hourly replay smooths away. "
                 "Sample days only; own-stack marginal, not the coupled clear."),
        "src": "https://www.iemop.ph/market-data/rtd-generation-offers/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        print(f"rtdoe5_replay: {len(out['days'])} sample days priced at 5-min")
    else:
        print("pass --derive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
