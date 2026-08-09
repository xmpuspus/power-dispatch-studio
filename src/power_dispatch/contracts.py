"""Settle a contract book against the modeled spot price.

A retail supplier, a plant owner, and an industrial buyer all ask the same
question about any scenario: what does it do to my position? The dispatch model
answers half of it, because it produces an hourly spot price per grid. The other
half is arithmetic on a contract book, and the book is the caller's.

One contract is a volume at a strike price over a set of hours:

    {"name": "PSA with the DU", "grid": "luzon", "mw": 250,
     "strike_php_kwh": 6.4, "hours": [18, 19, 20, 21], "side": "buy"}

`side` says which way the position runs. A **buy** contract fixes the price the
holder pays, so a spot price above the strike is a gain against buying at spot.
A **sell** contract fixes the price the holder receives, so the same spot move is
a loss. Omit `hours` and the contract covers all 24.

`settle` returns pesos, per contract and in total, and never guesses at volume
the book does not carry. It also reports the open position: the load a caller
declares and has not contracted, priced at spot.

What this is not: no credit terms, no take-or-pay, no capacity fee, no
line-rental or wheeling charge, and no tax. It marks energy against modeled spot
and nothing else. A settlement statement has more lines than this.

    import power_dispatch as pd
    r = pd.run_scenario({"date": "2026-06-17", "opts": {"fuel_avail_delta":
                        {"luzon": {"coal": -647}}}})
    pos = pd.settle(r, book, load_mw={"luzon": 400})
"""

from __future__ import annotations

GRIDS = ("luzon", "visayas", "mindanao")
SIDES = ("buy", "sell")


def validate_book(book: list) -> list[str]:
    """Every problem with a contract book, as messages a person can act on."""
    e: list[str] = []
    if not isinstance(book, list):
        return ["the contract book must be a list"]
    for i, c in enumerate(book):
        if not isinstance(c, dict):
            e.append(f"contract[{i}] must be an object")
            continue
        if c.get("grid") not in GRIDS:
            e.append(f"contract[{i}].grid must be one of {', '.join(GRIDS)}")
        for f in ("mw", "strike_php_kwh"):
            v = c.get(f)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                e.append(f"contract[{i}].{f} must be a number")
        if c.get("mw", 0) < 0:
            e.append(f"contract[{i}].mw must not be negative. Use side to pick direction")
        side = c.get("side", "buy")
        if side not in SIDES:
            e.append(f"contract[{i}].side must be buy or sell")
        hrs = c.get("hours")
        if hrs is not None:
            if not isinstance(hrs, list) or not hrs:
                e.append(f"contract[{i}].hours must be a non-empty list of hours")
            elif any(not isinstance(h, int) or h < 0 or h > 23 for h in hrs):
                e.append(f"contract[{i}].hours must hold whole hours from 0 to 23")
        if "name" in c and not isinstance(c["name"], str):
            e.append(f"contract[{i}].name must be a string")
    return e


def settle(result: dict, book: list, load_mw: dict | None = None) -> dict:
    """Mark a contract book against one solved day.

    `result` is what run_scenario returns. `load_mw` is the caller's own load
    per grid in MW, flat across the day, and it decides the open position.

    Every figure is pesos for the day. One MW held for one hour is one MWh, and
    a price in PhP/kWh is a thousand pesos per MWh, so the peso value of one
    contract-hour is mw * 1000 * price.
    """
    problems = validate_book(book)
    if problems:
        raise ValueError("contract book has problems:\n  " + "\n  ".join(problems))
    hours = result["hours"]
    n = len(hours)

    rows = []
    for c in book:
        g = c["grid"]
        cover = c.get("hours") or list(range(n))
        cover = [h for h in cover if h < n]
        mw = float(c["mw"])
        strike = float(c["strike_php_kwh"])
        sign = 1.0 if c.get("side", "buy") == "buy" else -1.0
        spot_cost = sum(hours[h]["price"][g] * mw * 1000.0 for h in cover)
        strike_cost = strike * mw * 1000.0 * len(cover)
        # a buy contract is worth what spot would have cost minus what it fixed
        rows.append(
            {
                "name": c.get("name") or f"{g} {mw:g} MW at P{strike:g}",
                "grid": g,
                "mw": mw,
                "strike_php_kwh": strike,
                "side": c.get("side", "buy"),
                "hours_covered": len(cover),
                "mwh": mw * len(cover),
                "spot_value_php": round(spot_cost, 2),
                "strike_value_php": round(strike_cost, 2),
                "position_php": round(sign * (spot_cost - strike_cost), 2),
                "mean_spot_php_kwh": round(
                    sum(hours[h]["price"][g] for h in cover) / len(cover), 4
                )
                if cover
                else 0.0,
            }
        )

    covered = {g: [0.0] * n for g in GRIDS}
    for c, r in zip(book, rows):
        if c.get("side", "buy") != "buy":
            continue
        for h in c.get("hours") or range(n):
            if h < n:
                covered[c["grid"]][h] += float(c["mw"])

    open_rows = []
    for g, mw in (load_mw or {}).items():
        if g not in GRIDS:
            continue
        open_mwh = 0.0
        open_cost = 0.0
        for h in range(n):
            gap = max(0.0, float(mw) - covered[g][h])
            open_mwh += gap
            open_cost += gap * 1000.0 * hours[h]["price"][g]
        open_rows.append(
            {
                "grid": g,
                "load_mw": float(mw),
                "open_mwh": round(open_mwh, 2),
                "open_cost_php": round(open_cost, 2),
                "covered_share_pct": round(
                    100.0 * (1 - open_mwh / (float(mw) * n)) if mw and n else 0.0, 1
                ),
            }
        )

    return {
        "date": result.get("summary", {}).get("date"),
        "hours": n,
        "contracts": rows,
        "position_php": round(sum(r["position_php"] for r in rows), 2),
        "open": open_rows,
        "open_cost_php": round(sum(r["open_cost_php"] for r in open_rows), 2),
        "note": (
            "Energy marked against modeled spot. No capacity fee, no wheeling "
            "charge, no tax, and no credit terms."
        ),
    }


def compare(base: dict, scenario: dict, book: list, load_mw: dict | None = None) -> dict:
    """What one scenario does to the position, which is the question people ask.

    Settles the same book twice and reports the change. A trip, a price move, or
    a new data center shows up here as pesos rather than as a price chart.
    """
    a = settle(base, book, load_mw)
    b = settle(scenario, book, load_mw)
    by_name = {r["name"]: r for r in a["contracts"]}
    moves = []
    for r in b["contracts"]:
        was = by_name.get(r["name"])
        if not was:
            continue
        moves.append(
            {
                "name": r["name"],
                "grid": r["grid"],
                "base_position_php": was["position_php"],
                "scenario_position_php": r["position_php"],
                "change_php": round(r["position_php"] - was["position_php"], 2),
                "base_mean_spot": was["mean_spot_php_kwh"],
                "scenario_mean_spot": r["mean_spot_php_kwh"],
            }
        )
    return {
        "base": a,
        "scenario": b,
        "contracts": moves,
        "position_change_php": round(b["position_php"] - a["position_php"], 2),
        "open_cost_change_php": round(b["open_cost_php"] - a["open_cost_php"], 2),
        "net_change_php": round(
            (b["position_php"] - a["position_php"])
            - (b["open_cost_php"] - a["open_cost_php"]),
            2,
        ),
        "note": a["note"],
    }
