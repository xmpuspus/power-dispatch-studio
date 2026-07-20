"""Bake the analyst-facing CSV exports from the already-baked web/data JSON.

The map and studio are the interactive front doors; these are the take-it-away
files an analyst pulls into a spreadsheet or their own model. Three tidy tables
plus an index that documents them, written to web/data/exports/ and served at
/data/exports/ (map) and /studio/data/exports/ (studio):

  congestion_league.csv  every named 230 kV equipment ranked by days at a limit
  backcast_by_grid.csv   both validation engines, per grid (the offer premium
                         is offer_replay.modeled minus cost_model.modeled)
  market_by_day.csv      the day-by-day archive feed: LWAP, spread, curtailment,
                         alerts, reserve price, and the day's binding equipment

Reads only the committed bake, no market fetch, so it runs in the same second as
build_data. build_data calls export_all() at the end of every bake.
"""

import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")
OUT = os.path.join(WEB, "exports")
GRIDS = ("luzon", "visayas", "mindanao")


def _load(name):
    with open(os.path.join(WEB, name)) as fh:
        return json.load(fh)


def _write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def _congestion_league(cong):
    header = [
        "equipment", "station", "voltage_kv", "days_bound",
        "rtd_intervals", "rtd_days", "dap_days", "max_overload_mw",
        "max_pct_of_limit",
    ]
    rows = [
        [e.get("equipment"), e.get("station"), e.get("voltage"), e.get("days"),
         e.get("rtd_intervals"), e.get("rtd_days"), e.get("dap_days"),
         e.get("max_overload_mw"), e.get("max_pct_of_limit")]
        for e in cong.get("league", [])
    ]
    return header, rows


def _backcast_by_grid(profiles):
    header = [
        "engine", "grid", "days", "observed_mean_php_kwh", "modeled_mean_php_kwh",
        "mae_php_kwh", "bias_php_kwh", "correlation", "high_hour_hit_rate_pct",
    ]
    rows = []
    for engine, key in (("offer_replay", "offer_backcast"), ("cost_model", "backcast")):
        bc = profiles.get(key) or {}
        per = bc.get("per_grid") or {}
        for g in GRIDS:
            s = per.get(g) or {}
            rows.append([
                engine, g, bc.get("days"),
                s.get("observed_mean_php_kwh"), s.get("modeled_mean_php_kwh"),
                s.get("mae_php_kwh"), s.get("bias_php_kwh"),
                s.get("correlation"), s.get("high_hour_hit_rate_pct"),
            ])
    return header, rows


def _market_by_day(drivers):
    header = [
        "date", "market",
        "luzon_lwap_php_kwh", "visayas_lwap_php_kwh", "mindanao_lwap_php_kwh",
        "spread_php_kwh",
        "luzon_curtailed_mwh", "visayas_curtailed_mwh", "mindanao_curtailed_mwh",
        "alert_advisories", "reserve_price_max_php_kwh", "rtd_binding_rows",
        "top_binding_equipment",
    ]
    rows = []
    for day in drivers.get("days", []):
        lwap = day.get("lwap") or {}
        cur = day.get("curtailed_mwh") or {}
        binding = day.get("binding") or {}
        top = ";".join(e.get("name", "") for e in binding.get("top_equipment", []))
        rows.append([
            day.get("date"), day.get("market"),
            lwap.get("luzon"), lwap.get("visayas"), lwap.get("mindanao"),
            day.get("spread"),
            cur.get("luzon"), cur.get("visayas"), cur.get("mindanao"),
            day.get("n_alert_advisories"), day.get("reserve_price_max"),
            binding.get("rtd_binding_rows"), top,
        ])
    return header, rows


def export_all():
    os.makedirs(OUT, exist_ok=True)
    cong = _load("congestion.json")
    profiles = _load("profiles.json")
    drivers = _load("drivers.json")
    meta = _load("meta.json")

    specs = [
        ("congestion_league.csv", _congestion_league(cong),
         "Every named 230 kV equipment the operator held at a limit in the window, "
         "ranked by days bound. Source: IEMOP RTDCV + DAPCV."),
        ("backcast_by_grid.csv", _backcast_by_grid(profiles),
         "Both validation engines per grid over the market-priced window. The offer "
         "premium is the offer_replay modeled mean minus the cost_model modeled mean."),
        ("market_by_day.csv", _market_by_day(drivers),
         "The day-by-day archive feed: observed LWAP, island spread, curtailment, "
         "alert advisories, peak reserve price, and the day's binding equipment."),
    ]

    index = {
        "built_utc": meta.get("built_utc"),
        "window": cong.get("window"),
        "note": (
            "Tidy CSV exports baked from public IEMOP files. Free to reuse under "
            "CC-BY-4.0; cite Power Dispatch Studio. Regenerated on every bake."
        ),
        "files": [],
    }
    for fname, (header, rows), desc in specs:
        n = _write(fname, header, rows)
        index["files"].append(
            {"file": fname, "rows": n, "columns": header, "description": desc}
        )

    with open(os.path.join(OUT, "index.json"), "w") as fh:
        json.dump(index, fh, indent=1)
    return index


if __name__ == "__main__":
    idx = export_all()
    for f in idx["files"]:
        print(f"{f['file']}: {f['rows']} rows")
