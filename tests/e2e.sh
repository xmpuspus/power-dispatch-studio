#!/bin/zsh
# Behavioral checks against the running map. Usage: zsh tests/e2e.sh [BASE]
# Start the server first: make serve &
set -u
# 127.0.0.1, never localhost. localhost resolves to ::1 first on macOS and on
# GitHub runners, web/serve.py binds 127.0.0.1 only, and every request pays a
# failed IPv6 attempt before falling back. On a cold server that fallback is
# slow enough to fail the first check, which is the "GET /" flake.
BASE="${1:-http://127.0.0.1:8789}"
pass=0; fail=0
ok(){ echo "PASS $1"; pass=$((pass+1)); }
bad(){ echo "FAIL $1"; fail=$((fail+1)); }

code(){ curl -s -o /dev/null -w '%{http_code}' "$BASE$1"; }

# 1) pages and every generated file return HTTP 200
for p in / /methodology.html /for-analysts.html; do
  [ "$(code $p)" = "200" ] && ok "GET $p" || bad "GET $p"
done
for f in meta.json answers.json congestion.json prices.json reliability.json \
         outages.json market_anchors.json demand_anchors.json \
         dipcef_congestion_sample.json chokepoints.geojson dc_sites.geojson sual.geojson \
         generators.geojson dispatch.json grid_lines.geojson grid_nodes.geojson \
         grid.json nodal_obs.json; do
  [ "$(code /data/$f)" = "200" ] && ok "GET /data/$f" || bad "GET /data/$f"
done

# 2) structural JSON assertions
python3 - "$BASE" <<'PY'
import json, sys, urllib.request
base = sys.argv[1]
def get(p):
    with urllib.request.urlopen(base + p) as r:
        return json.load(r)
checks = []
ans = get("/data/answers.json")
checks.append(("answers has q1/q2/q3", all(k in ans for k in ("q1","q2","q3"))))
# the take-it-away CSVs: the README and the map both point here, so a missing
# index or a renamed file has to fail a command, not a reader's click
ex = get("/data/exports/index.json")
exf = ex.get("files") if isinstance(ex, dict) else None
checks.append(("exports index documents 3 CSVs", isinstance(exf, list) and len(exf) == 3))
for name in ("market_by_day.csv", "congestion_league.csv", "backcast_by_grid.csv"):
    checks.append((f"export {name} is documented", any(
        name in json.dumps(x) for x in (exf or []))))
ck = get("/data/chokepoints.geojson")
checks.append(("5 chokepoint features", len(ck["features"]) == 5))
checks.append(("corridors ride real routes", all(
    f["properties"].get("route") == "osm-mapped" for f in ck["features"])))
gl = get("/data/grid_lines.geojson")
checks.append(("grid lines served (>=1200)", len(gl["features"]) >= 1200))
gn = get("/data/grid_nodes.geojson")
checks.append(("grid nodes served (>=450)", len(gn["features"]) >= 450))
no = get("/data/nodal_obs.json")
checks.append(("nodal deviations served (>=1000 nodes, >=200 placed)",
               no.get("available") is True and no.get("n_nodes", 0) >= 1000
               and no.get("n_placed", 0) >= 200))
dc = get("/data/dc_sites.geojson")
checks.append(("14 dc features", len(dc["features"]) == 14))
cong = get("/data/congestion.json")
checks.append(("league present", len(cong.get("league", [])) >= 10))
fnd = get("/data/findings.json")
checks.append(("findings drawer generated (>=5)", len(fnd.get("findings", [])) >= 5))
checks.append(("every finding has a map focus", all(
    f.get("focus", {}).get("center") and f["focus"].get("mode")
    for f in fnd.get("findings", []))))
lc = cong.get("corridor_receipts", {}).get("leyte_cebu_230kv", {})
checks.append(("Leyte-Cebu corridor receipts joined", lc.get("days", 0) >= 60))
gens = get("/data/generators.geojson")
checks.append(("11 named generators", len(gens["features"]) == 11))
disp = get("/data/dispatch.json")
checks.append(("dispatch model available", disp.get("available") is True))
checks.append(("dispatch calibration 3 grids",
               set(disp.get("calibration", {})) == {"luzon","visayas","mindanao"}))
checks.append(("N-1 table covers 11 units", len(disp.get("n1", [])) == 11))
checks.append(("merit-order stacks generated", all(
    (disp.get("merit_order", {}).get(g, {}).get("blocks"))
    for g in ("luzon","visayas","mindanao"))))
cpl = disp.get("coupling", {})
checks.append(("coupling block generated (spread decomposition + corridors)",
               bool(cpl.get("spread_decomposition")) and len(cpl.get("corridors", [])) == 2
               and cpl.get("outage_scenario", {}).get("leyte_luzon_saturated_pct") is not None))
mc = disp.get("reliability_mc", {})
checks.append(("reliability MC + unit commitment generated",
               mc.get("draws", 0) >= 2000
               and mc.get("dict_2028_luzon", {}).get("distribution", {}).get("lolp_pct") is not None
               and bool(disp.get("unit_commitment", {}).get("per_grid"))))
stg = disp.get("storage", {})
checks.append(("storage block generated (assets + buyback)",
               stg.get("assets", {}).get("luzon", {}).get("total_mw") == 1319
               and stg.get("reliability_buyback", {}).get("luzon_dict_2028") is not None))
checks.append(("price-duration + marginal-frequency generated",
               bool(disp.get("price_duration", {}).get("luzon", {}).get("observed"))
               and bool(disp.get("marginal_frequency", {}).get("luzon", {}).get("by_block"))))
html = urllib.request.urlopen(base + "/").read().decode()
checks.append(("page mentions the three questions",
               "How large is announced demand" in json.dumps(ans)
               and "Power Dispatch Studio" in html))
checks.append(("public map does not expose a second scenario calculator",
               'data-mode="simulate"' not in html and 'id="sualbtn"' not in html))
checks.append(("public map links to the analyst studio",
               'href="studio/#v=' in html))
checks.append(("disclaimer on page", "legitimate explanations" in html))
checks.append(("og:image tag present", 'property="og:image"' in html))
checks.append(("findings drawer markup present", 'id="findings"' in html))
bad = [n for n, c in checks if not c]
for n, c in checks:
    print(("PASS " if c else "FAIL ") + n)
sys.exit(1 if bad else 0)
PY
[ $? -eq 0 ] && ok "json structural block" || bad "json structural block"

# 3) browser block (only if agent-browser is installed)
strip(){ tail -1 | sed $'s/\x1b\\[[0-9;]*m//g' | tr -d '"\\'; }
if command -v agent-browser >/dev/null 2>&1; then
  agent-browser close >/dev/null 2>&1; sleep 2
  agent-browser open "$BASE/" >/dev/null 2>&1; sleep 6
  R=$(agent-browser eval 'const d=window.__diag||{};[d.ready,d.chokepoints,d.dcs,d.league>0,d.mode].join("|")' 2>/dev/null | strip)
  echo "diag: $R"
  [[ "$R" == true\|5\|14\|true\|* ]] && ok "browser __diag ready+layers" || bad "browser __diag ($R)"
  G=$(agent-browser eval 'const d=window.__diag||{};[d.gridLines>=1200,d.gridNodes>=450].join("|")' 2>/dev/null | strip)
  [[ "$G" == "true|true" ]] && ok "browser grid layers loaded" || bad "browser grid layers ($G)"
  agent-browser eval 'document.querySelector("[data-mode=choke]").click()' >/dev/null 2>&1
  sleep 1
  GV=$(agent-browser eval 'map.getLayoutProperty("grid-230","visibility")||"visible"' 2>/dev/null | strip)
  [[ "$GV" == "visible" ]] && ok "grid visible in choke mode" || bad "grid visibility in choke ($GV)"
  agent-browser eval 'document.querySelector("[data-mode=price]").click()' >/dev/null 2>&1
  sleep 1
  M=$(agent-browser eval '(window.__diag||{}).mode' 2>/dev/null | strip)
  [[ "$M" == "price" ]] && ok "mode switch to price" || bad "mode switch ($M)"
  NP=$(agent-browser eval 'const d=window.__diag||{};[d.nodalPlaced>=200, map.getLayoutProperty("nodal-pt","visibility")||"visible"].join("|")' 2>/dev/null | strip)
  [[ "$NP" == "true|visible" ]] && ok "nodal deviation layer live in price mode" || bad "nodal layer ($NP)"
  # findings drawer opens and a card flies to its evidence (mode + URL follow)
  agent-browser eval 'document.getElementById("fopen").click(); document.querySelectorAll("#flist .fcard")[0].click()' >/dev/null 2>&1
  sleep 1
  FD=$(agent-browser eval 'const d=window.__diag||{};[d.findings>=5,d.drawerOpen,!!d.activeFinding,location.search.includes("finding")].join("|")' 2>/dev/null | strip)
  echo "drawer: $FD"
  [[ "$FD" == true\|true\|true\|true ]] && ok "findings drawer + deep-link" || bad "findings drawer ($FD)"
  # drivers mode: the day-by-day timeline renders rows and the week-ahead block
  agent-browser eval 'document.querySelector(".mode[data-mode=drivers]").click()' >/dev/null 2>&1
  sleep 1
  DV=$(agent-browser eval '[window.__diag.mode, (window.__diag.driversDays||0)>20, document.querySelectorAll("details.drv").length>10].join("|")' 2>/dev/null | strip)
  echo "drivers: $DV"
  [[ "$DV" == drivers\|true\|true ]] && ok "drivers timeline renders day rows" || bad "drivers mode ($DV)"
  agent-browser close >/dev/null 2>&1
else
  echo "SKIP browser block (agent-browser not installed)"
fi

echo "e2e: $pass pass, $fail fail"
exit $([ $fail -eq 0 ] && echo 0 || echo 1)
