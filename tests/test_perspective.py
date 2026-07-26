#!/usr/bin/env python3
"""Pins on web/data/perspective.json, the numbers behind web/pax-silica.html.

Plain python, PASS/FAIL per pin, exit 1 on any FAIL. The page renders these
numbers directly, so a drifted bake here is a wrong public claim there.

The dashboard bars are rendered by the page's own JavaScript from this same
JSON at load time, so they cannot drift from it. The prose around them is
hand-typed, and does not re-read the bake, so a re-run that shifts a number
(the line limit moves with the day, the archive window grows nightly) can
leave the static text quietly wrong while the bars above it are correct.
check_html_static_text() catches that: it strips the page's <script> block
and asserts the bake's formatted values still appear in what is left.
"""
import json
import math
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
PATH = os.path.join(ROOT, "web", "data", "perspective.json")
HTML_PATH = os.path.join(ROOT, "web", "pax-silica.html")

fails = []


def pin(name, ok, detail=""):
    print(("[PASS] " if ok else "[FAIL] ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def check_html_static_text(c, p, s, w, wa, pr):
    if not os.path.exists(HTML_PATH):
        pin("pax-silica.html present", False)
        return
    html = open(HTML_PATH).read()
    static = re.sub(r"<script>.*?</script>", "", html, flags=re.S)
    # match against whitespace-flattened text so a prose rewrap cannot break
    # a pin whose phrase merely moved across a line boundary
    flat = re.sub(r"\s+", " ", static)

    def has(label, needle):
        pin(f"static prose carries: {label}", needle in flat, needle)

    has("campus 3,000 MW", f"{c['mw']:,.0f} MW")
    has("campus water range", f"{c['water_mld'][0]:.0f} to {c['water_mld'][1]:.0f} million liters")
    has("acwa daily share", f"{s['acwa_share_pct']}%")
    has("sun-alone nameplate", f"{s['sun_alone_mw']:,.0f} MW")
    has("sun-alone land, prose", f"{s['sun_alone_km2']:.0f} square kilometers")
    # the land chart projects the panel area onto a real basemap: guard that
    # the overlay's size comes from the bake and the map is attributed
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    pin("map overlay side computed from the baked km2",
        "Math.sqrt(P.sun.sun_alone_km2) * 1000 / mpp" in script)
    pin("basemap attribution present",
        "OpenStreetMap contributors" in script and "CARTO" in script)
    has("water people-equivalent",
        f"{wa['people_equiv'][0]:,.0f} to {wa['people_equiv'][1]:,.0f} people")
    has("water rice hectares",
        f"{wa['rice_ha'][0]:,.0f} to {wa['rice_ha'][1]:,.0f} hectares")
    has("water Angat share",
        f"{wa['angat_share_pct'][0]} to {wa['angat_share_pct'][1]} percent")
    has("Makati 2024 population", f"{wa['makati_pop_2024']:,}")
    has("modeled base price", f"P{pr['luzon_mean'][0]:.2f} per kWh")
    has("modeled with-campus price", f"P{pr['luzon_mean'][1]:.2f}")
    has("modeled Visayas peak pulled up", f"P{pr['visayas_peak'][1]:.2f}")
    has("modeled congestion rent",
        f"P{round(pr['links_rent_m_php'][1])} million of congestion rent")
    has("DIPCEF sample size",
        f"{pr['dipcef']['days_nonzero']} of {pr['dipcef']['days_sampled']} sampled days")
    has("DIPCEF median", f"P{pr['dipcef']['median_php_kwh']} per kWh")
    has("passthrough peso line", f"P{pr['passthrough_php_month']:,} a month")
    has("olympic pool basis", "an Olympic pool holds 2.5 million liters")
    has("island population source", "2020 census via Wikipedia")
    has("substation cost", f"P{w['substation']['php_b']} billion")
    has("Hermosa-San Jose cost", f"P{w['hsj']['php_b']} billion")
    has("Mindanao-Visayas cost", f"P{w['mvip']['php_b']:.0f} billion")
    # the own-station scenario's uncovered MW is arithmetic on the same line
    # limit the dashboard bar reads live; the static paragraph and the ledger
    # table both name it in prose, so both must track it by hand
    missing = round(c["mw"] - 1900 - w["limit_7pm_mw"])
    has("own-station shortfall (paragraph + ledger)", f"{missing} MW")
    pin("own-station shortfall appears exactly twice (paragraph, ledger)",
        static.count(f"{missing} MW has no source"
                     ) + static.count(f"{missing} MW of campus has no") == 2)

    # every source URL the bake carries must appear as a link on the page, so
    # a claim can never outlive the citation it was built on
    urls = set()
    for section in (c, p, s, w, wa):
        for v in section["src"].values():
            urls.update(re.findall(r"https?://[^\s;)]+", v))
    unlinked = sorted(u for u in urls if u not in html)
    pin(f"all {len(urls)} baked source URLs are linked on the page",
        not unlinked, "; ".join(unlinked[:3]))


def main():
    if not os.path.exists(PATH):
        print("[FAIL] perspective.json missing; run python3 pipeline/perspective.py")
        sys.exit(1)
    d = json.load(open(PATH))

    c, p, s, w, wa = d["campus"], d["power"], d["sun"], d["wires"], d["water"]
    pr = d["price"]

    pin("campus 3,000 MW announced figure", math.isclose(c["mw"], 3000.0))
    pin("energy is 72 GWh/day (3,000 x 24)", math.isclose(c["energy_gwh_day"], 72.0))
    pin("water range is BCDA's 65-90 MLD", c["water_mld"] == [65.0, 90.0])

    pk = p["archive_peaks_mw"]
    pin("archive peaks present for all three grids",
        all(k in pk for k in ("luzon", "visayas", "mindanao")))
    pin("campus exceeds Visayas archive peak", c["mw"] > pk["visayas"],
        f"{pk['visayas']}")
    pin("campus exceeds NGCP June Visayas available capacity",
        c["mw"] > p["visayas_bulletin"]["avail_hi"])
    pin("Luzon peak in a sane band (13-16 GW)", 13000 < pk["luzon"] < 16000,
        f"{pk['luzon']}")
    pin("homes arithmetic: 72 GWh/day over 200 kWh/month",
        abs(p["homes_million"] - round(
            c["mw"] * 24 * 1000 / (p["home_kwh_month"] / 30.4166) / 1e6, 1)) < 0.05)

    pin("acwa covers 4-5% of the campus day (cloudless)",
        3.5 <= s["acwa_share_pct"] <= 5.0, f"{s['acwa_share_pct']}%")
    pin("sun-alone nameplate = demand over cloudless CF",
        abs(s["sun_alone_mw"] - round(c["mw"] / s["cf_cloudless"], -2)) < 1,
        f"{s['sun_alone_mw']}")
    pin("sun-alone land uses Terra's 1.0 ha/MW",
        abs(s["sun_alone_km2"] - round(s["sun_alone_mw"] / 100, 0)) < 1)
    pin("land comparisons consistent with areas",
        abs(s["vs_makati"] - round(s["sun_alone_km2"] / s["makati_km2"], 1)) < 0.05
        and abs(s["vs_ncc"] - round(s["sun_alone_km2"] / s["ncc_km2"], 2)) < 0.01)
    pin("night bridge vs Terra BESS ratio consistent",
        abs(s["vs_terra_bess"] - round(s["bridge_gwh"] * 1000 / 4500, 1)) < 0.05)

    pin("7pm line limit within the baked hourly band",
        w["limit_min_mw"] <= w["limit_7pm_mw"] <= w["limit_max_mw"],
        f"{w['limit_7pm_mw']}")
    pin("gap = campus - limit", w["gap_mw"] == round(c["mw"] - w["limit_7pm_mw"], 0))
    pin("site is radially fed in the model", w["radially_fed"] is True)
    pin("substation is the announced P6.95B 230 kV end-2028",
        w["substation"] == {"php_b": 6.95, "kv": 230, "year": 2028})

    pin("price: modeled on the same recorded day as the wires limit",
        pr["day"] == w["day"])
    pin("price: with-campus Luzon mean is roughly double the base",
        1.5 <= pr["luzon_mean"][1] / pr["luzon_mean"][0] <= 3.0,
        f"{pr['luzon_mean']}")
    pin("price: campus raises the inter-island congestion rent",
        pr["links_rent_m_php"][1] > pr["links_rent_m_php"][0],
        f"{pr['links_rent_m_php']}")
    pin("price: DIPCEF stats carried as stated in methodology",
        pr["dipcef"]["days_nonzero"] == 28
        and pr["dipcef"]["days_sampled"] == 70
        and math.isclose(pr["dipcef"]["median_php_kwh"], 0.56))

    mer = pr["merit"]
    pin("merit ladder: blocks are cost-ordered and contiguous",
        all(mer["blocks"][i]["cost"] <= mer["blocks"][i + 1]["cost"]
            and mer["blocks"][i]["cum_to"] == mer["blocks"][i + 1]["cum_from"]
            for i in range(len(mer["blocks"]) - 1)))
    def landing(mw):
        return next(b for b in mer["blocks"]
                    if b["cum_from"] < mw <= b["cum_to"])
    pin("merit ladder: today's evening demand lands on the P6 coal block",
        math.isclose(landing(mer["evening_demand_mw"])["cost"], 6.0))
    pin("merit ladder: demand with the campus lands on the P12 oil block",
        math.isclose(landing(mer["demand_with_campus_mw"])["cost"], 12.0))
    pin("merit ladder: campus delta is the announced 3,000 MW",
        mer["demand_with_campus_mw"] - mer["evening_demand_mw"] == 3000)

    pin("perspective anchors: pools, own-gap homes, passthrough, island people",
        wa["pools_per_day"] == [round(65 / 2.5), round(90 / 2.5)]
        and abs(w["own_gap_homes_million"] - round(
            (c["mw"] - 1900 - w["limit_7pm_mw"]) * 24 * 1000
            / (p["home_kwh_month"] / 30.4166) / 1e6, 1)) < 0.05
        and pr["passthrough_php_month"] == round((12.0 - 6.0) * p["home_kwh_month"])
        and set(p["island_pop_m"]) == {"luzon", "visayas", "mindanao"})

    pin("solar: 24 hourly cover values, evening zero, midday sliver",
        len(s["hourly_cover_pct"]) == 24
        and s["hourly_cover_pct"][19] == 0
        and 10 <= max(s["hourly_cover_pct"]) <= 15)

    pin("water people range = MLD over 150 L/person",
        wa["people_equiv"] == [round(65e6 / 150, -3), round(90e6 / 150, -3)],
        f"{wa['people_equiv']}")
    pin("Makati multiple uses the 2024 census (post-Embo)",
        wa["makati_pop_2024"] == 309770
        and wa["vs_makati_people"][1] == round(600000 / 309770, 1))
    pin("rice hectares from FAO 12-15 ML/ha/season over 120 days",
        wa["rice_ha"] == [round(65 / (15 / 120), -1), round(90 / (12 / 120), -1)],
        f"{wa['rice_ha']}")
    pin("Angat share stays a small percent (1-3%)",
        1.0 <= wa["angat_share_pct"][0] <= wa["angat_share_pct"][1] <= 3.0)

    for section in (c, p, s, w, wa):
        pin("sources block present in every section", "src" in section)
        break
    pin("every section carries src URLs",
        all("src" in x and x["src"] for x in (c, p, s, w, wa, pr)))

    check_html_static_text(c, p, s, w, wa, pr)

    print()
    if fails:
        print(f"{len(fails)} FAIL")
        sys.exit(1)
    print("all perspective pins pass")


if __name__ == "__main__":
    main()
