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
import html as html_lib
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


def check_html_static_text(c, p, s, w, wa, pr, SITE):
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
    has("the paddy duty is named beside the hectares it produces",
        f"{wa['rice_l_s_ha']} liters")
    has("water Angat share",
        f"{wa['angat_share_pct'][0]} to {wa['angat_share_pct'][1]} percent")
    has("Makati 2024 population", f"{wa['makati_pop_2024']:,}")
    has("modeled base price", f"P{pr['luzon_mean'][0]:.2f} per kWh")
    has("modeled with-campus price", f"P{pr['luzon_mean'][1]:.2f}")
    has("modeled Visayas peak pulled up", f"P{pr['visayas_peak'][1]:.2f}")
    # the card says this in plain words now, so the pin follows the number
    has("modeled congestion rent",
        f"about P{round(pr['links_rent_m_php'][1])} million in this one modeled day")
    has("DIPCEF sample size",
        f"{pr['dipcef']['days_nonzero']} of {pr['dipcef']['days_sampled']} sampled days")
    has("DIPCEF median", f"P{pr['dipcef']['median_php_kwh']} per kWh")
    has("DIPCEF maximum, to the precision the sweep measured",
        f"P{pr['dipcef']['max_php_kwh']} on")
    has("passthrough peso line", f"P{pr['passthrough_php_month']:,} a month")
    has("olympic pool basis", "an Olympic pool holds 2.5 million liters")
    has("island population source", "Island populations, 2020 census")
    has("substation cost", f"P{w['substation']['php_b']} billion")
    has("Hermosa-San Jose cost", f"P{w['hsj']['php_b']} billion")
    has("Mindanao-Visayas cost", f"P{w['mvip']['php_b']:.0f} billion")
    # the own-station scenario's uncovered MW is arithmetic on the same line
    # limit the dashboard bar reads live; the static paragraph and the ledger
    # table both name it in prose, so both must track it by hand
    missing = round(c["mw"] - (w["own_station_mw"] - w["trip_unit_mw"])
                    - w["limit_7pm_mw"])
    pin("own-station shortfall is derived in the bake, not typed here",
        w["own_gap_mw"] == missing)
    has("own-station shortfall (paragraph + ledger)", f"{missing} MW")
    pin("own-station shortfall appears in the paragraph, the title and the ledger",
        static.count(f"{missing} MW") >= 3)
    has("own-station size is named as a choice", f"{w['own_station_mw']:,.0f} MW station")
    has("tripped-unit size is named as a choice", f"{w['trip_unit_mw']:,.0f} MW unit")

    # the delivery limit is the page's most-quoted model output and it moves with
    # every re-bake, so both the exact figure and the rounded one it is written as
    has("line limit, exact", f"{w['limit_7pm_mw']:,.0f} MW")
    has("line limit, rounded, in the section heading",
        f"{round(w['limit_7pm_mw'], -1):,.0f} of the {c['mw']:,.0f} MW")
    has("shortfall against the announced draw", f"{w['gap_mw']:,.0f} MW")
    has("class rating per circuit", f"{w['circuit_rating_mw']:,.0f} MW")

    # the archive numbers are recomputed on every nightly bake, so the prose that
    # names them has to be pinned or the cron silently falsifies it
    has("archived day count", f"{p['archive_days']} archived days")
    has("Luzon archive peak", f"{p['archive_peaks_mw']['luzon']:,} MW")
    has("Visayas archive peak", f"{p['archive_peaks_mw']['visayas']:,}")
    for k in ("peak_lo", "peak_hi", "avail_lo", "avail_hi"):
        has(f"Visayas bulletin {k}", f"{p['visayas_bulletin'][k]:,}")

    # the price card states which fuel sets the price in how many hours; the
    # count comes from the solve and must not be asserted in prose
    mw_ = pr["marginal_wave"]
    has("marginal-hour count with the wave",
        f"in {mw_['top_hours']} of those hours")
    pin("the base case is coal in every hour",
        pr["marginal_base"]["top"] == "coal"
        and pr["marginal_base"]["top_hours"] == 24)
    has("headroom left in the stack",
        f"{pr['merit']['headroom_with_campus_mw']:,.0f} MW of the")
    # both cost anchors are settlement prices, so the page must name the setter
    # of the coal one and must never call either a measured fuel cost
    has("the coal price names its regulator and resolution",
        "Resolution No. 10, Series of 2026")
    pin("the page never claims no price setter exists",
        "names no price setter" not in static)
    pin("the 770 MW is never credited to both routes at once",
        "two existing 230 kV routes deliver" not in flat
        and "two existing power routes can carry" not in flat)

    # every source URL the bake carries must appear as a link on the page, so
    # a claim can never outlive the citation it was built on
    urls = set()
    for section in (c, p, s, w, wa, pr, SITE):
        for v in section["src"].values():
            urls.update(re.findall(r"https?://[^\s;)]+", v))
    unlinked = sorted(u for u in urls if u not in html)
    pin(f"all {len(urls)} baked source URLs are linked on the page",
        not unlinked, "; ".join(unlinked[:3]))

    # no card may fall back to the methodology page instead of naming the source
    pin("no chart leans on a methodology link instead of a real source",
        "methodology.html" not in html)
    # every card footnotes the public sources a reader can open, and that
    # footnote carries citable URLs, never a path inside this repo
    cards = re.findall(r'id="(fig-[a-z]+)"(.*?)\n</div>', html, re.S)
    bad = []
    for cid, body in cards:
        m = re.search(r'<p class="rawline">Sources:(.*?)</p>', body, re.S)
        if not m:
            bad.append(cid + ":no-sources-footnote")
            continue
        links = re.findall(r'href="(https?://[^"]+)"', m.group(1))
        if len(links) < 2:
            bad.append(cid + ":under-2-links")
        if any("github.com" in u for u in links):
            bad.append(cid + ":repo-path-in-footnote")
    pin(f"all {len(cards)} cards footnote citable public sources",
        len(cards) == 9 and not bad, ", ".join(bad))

    # a card gets screenshotted on its own, so a definition sitting on another
    # card is no definition at all: every acronym a card uses is spelled out on
    # that same card, between its <div class="fig"> and its own Sources line
    gloss = {
        "BCDA": "Bases Conversion and Development Authority",
        "NGCP": "National Grid Corporation of the Philippines",
        "IEMOP": "Independent Electricity Market Operator",
        "PSA": "Philippine Statistics Authority",
        "NWRB": "National Water Resources Board",
        "ERC": "Energy Regulatory Commission",
        "MW": "megawatt", "MWh": "megawatt-hour", "GW": "gigawatt",
        "kV": "kilovolt", "kWh": "kilowatt-hour",
        "MLD": "million liters", "CMS": "cubic meters per second",
    }
    undefined = []
    for m in re.finditer(r'<div class="fig[^"]*" id="(fig-[a-z]+)"', html):
        stop = html.index("</p>", html.index('class="rawline"', m.start()))
        # URLs carry acronyms nobody reads as words
        seen = re.sub(r"https?://\S+", " ",
                      re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
                                                 html[m.start():stop])))
        for acr, full in gloss.items():
            used = re.search(r"(?<![A-Za-z])" + acr + r"(?![A-Za-z])", seen)
            if used and full.lower() not in seen.lower():
                undefined.append(f"{m.group(1)}:{acr}")
    pin("every acronym is spelled out on the card that uses it",
        not undefined, ", ".join(undefined))

    # the subject is named, never pointed at: "the campus" reads fine in place
    # and means nothing in a screenshot, a link preview, or a shared card
    body = html.split("<body>", 1)[1].split("<script>", 1)[0]
    vague = re.findall(r"\bthe (?:campus|site)\b", re.sub(r"\s+", " ", body))
    pin("no reader-facing line leans on 'the campus' or 'the site' instead of naming it",
        not vague, f"{len(vague)} left")

    # the walkthrough doc's headings are the chart titles, verbatim and in order,
    # because Xavier reads the doc as the map of what each chart says
    def flat_title(s):
        s = re.sub(r"<[^>]+>", "", s)
        s = html_lib.unescape(s)          # the page writes km&#178;
        return re.sub(r"\s+", " ", s).strip()

    titles = [flat_title(m) for m in
              re.findall(r'<div class="figtitle">(.*?)</div>', html, re.S)]
    doc_path = os.path.join(ROOT, "docs", "pax-silica-visuals.md")
    if os.path.exists(doc_path):
        heads = re.findall(r"^## (.+)$", open(doc_path).read(), re.M)
        # the doc opens on the montage and closes on the limitations, neither of
        # which is a chart
        chart_heads = [h.strip() for h in heads if h.strip() in titles]
        missing = [t for t in titles if t not in [h.strip() for h in heads]]
        pin(f"all {len(titles)} chart titles appear verbatim as doc headings",
            len(titles) == 9 and not missing, "; ".join(missing[:2]))
        pin("doc headings carry the chart titles in the page's own order",
            chart_heads == [t for t in titles if t in chart_heads])
    # the land card: area against area, and the two absences it must keep saying
    # out loud. It may never start claiming a tree count or a certificate that
    # nobody has published.
    site = SITE
    pin("site area is the announced 1,620 hectares", site["ha"] == 1620.0)
    pin("site share of New Clark City is derived, not typed",
        site["share_of_ncc_pct"] == round(site["ha"] / site["ncc_ha"] * 100, 1))
    pin("site vs Makati is derived from both areas",
        site["vs_makati"] == round(site["ha"] / site["makati_ha"], 2))
    pin("no tree count is claimed", site["tree_count_published"] is False)
    pin("the masterplan certificate is recorded as issued, not as absent",
        site["ecc_masterplan_issued"] is True
        and site["ecc_per_locator_pending"] is True)
    has("the page states the masterplan certificate was issued",
        "compliance certificate for the project masterplan")
    has("the page states each locator still needs its own", "must still get its own")
    pin("no reader-facing line says a certificate has not been issued",
        "no environmental compliance certificate has been issued" not in static.lower())
    for b in site["pap_barangays"]:
        has(f"affected-persons barangay {b}", b)
    has("the local watershed is named on the water card", site["local_watershed"])
    has("site card states the tree count does not exist", "tree count does not exist")
    has("site card BCDA farmer figure", f"about {site['farmers_bcda']} farmers")
    has("site card advocacy displacement pair",
        f"{site['displaced_advocacy'][0]:,} Indigenous people and")
    has("site card Capas farmland share",
        f"over {site['capas_farmland_pct']:.0f} percent of Capas")
    has("site area in prose", f"{site['ha']:,.0f} hectares")
    has("site share of New Clark City in prose",
        f"{site['share_of_ncc_pct']} percent of the city by area")
    pin("the drawn square count is stated beside the exact share, so a reader "
        "can see the rounding",
        f"{round(site['ha'] / 50)} of the {round(site['ncc_ha'] / 50)} squares"
        in static)
    has("jobs figure, so the page is not one-sided",
        f"{c['jobs_direct'][0]:,} to {c['jobs_direct'][1]:,} direct jobs")
    has("the full-development horizon",
        f"{c['full_build_years'][0]} to {c['full_build_years'][1]} years")
    has("site card keeps the two people-counts apart", "cannot be subtracted")
    pin("the two displacement figures are stored as the advocacy pair",
        site["displaced_advocacy"] == [20000, 15000] and site["farmers_bcda"] == 10)

    # the failure scenario cites the measured outage record
    orec = w["outages"]
    pin("outage record: named units with measured days out",
        orec["days_in_window"] == 105 and len(orec["units"]) >= 2
        and all(u["days_out"] > 0 and u["mw"] > 300 for u in orec["units"]),
        f"{[(u['mw'], u['days_out']) for u in orec['units']]}")
    has("outage evidence on the card", "archived days")


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
    # the cost and the facility come from NGCP's plan; the date is BCDA's target.
    # The page must not merge the two owners, so the bake keeps them apart.
    sub = w["substation"]
    pin("substation is the announced P6.95B 230 kV end-2028",
        sub["php_b"] == 6.95 and sub["kv"] == 230 and sub["year"] == 2028)
    pin("the substation cost and the substation date carry different owners",
        sub["cost_owner"] == "NGCP transmission development plan"
        and sub["date_owner"] == "BCDA target")

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
    # the FAO manual the page cites prints one paddy figure, Table 1's 1.5 l/s/ha.
    # It carries no season total in millimeters, so the hectares must come from
    # that duty and nothing else.
    duty = wa["rice_l_s_ha"] * 86400 / 1e6
    pin("rice hectares come from the FAO paddy duty the cited page prints",
        wa["rice_l_s_ha"] == 1.5
        and wa["rice_ha"] == [round(65 / duty, -1), round(90 / duty, -1)],
        f"{wa['rice_ha']}")
    pin("Angat share stays a small percent (1-3%)",
        1.0 <= wa["angat_share_pct"][0] <= wa["angat_share_pct"][1] <= 3.0)

    for section in (c, p, s, w, wa):
        pin("sources block present in every section", "src" in section)
        break
    pin("every section carries src URLs",
        all("src" in x and x["src"] for x in (c, p, s, w, wa, pr)))

    check_html_static_text(c, p, s, w, wa, pr, d["site"])

    print()
    if fails:
        print(f"{len(fails)} FAIL")
        sys.exit(1)
    print("all perspective pins pass")


if __name__ == "__main__":
    main()
