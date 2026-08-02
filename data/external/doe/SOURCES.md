# DOE List of Existing Power Plants (grid-connected)

The primary source is the Philippine Department of Energy's per-grid PDFs,
"List of Existing Power Plants (Grid-Connected)." doe.gov.ph and legacy.doe.gov.ph
return 403 to non-PH requests, so the files here are the Internet Archive's
captures of the DOE's own URLs. Retrieved 2026-07-06.

| Grid | As of | DOE URL | Wayback capture |
|---|---|---|---|
| Luzon | 2025-04-30 | legacy.doe.gov.ph/sites/default/files/pdf/electric_power/01_Luzon%20Grid_2.pdf | https://web.archive.org/web/20251104021000/https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/01_Luzon%20Grid_2.pdf |
| Visayas | 2025-03-31 | legacy.doe.gov.ph/sites/default/files/pdf/electric_power/02_%20Visayas%20Grid.pdf | https://web.archive.org/web/20250515115334/https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/02_%20Visayas%20Grid.pdf |
| Mindanao | 2025-04-30 | legacy.doe.gov.ph/sites/default/files/pdf/electric_power/03_Mindanao%20Grid_2.pdf | https://web.archive.org/web/20250712234701/https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/03_Mindanao%20Grid_2.pdf |

The `.txt` files are `pdftotext -layout` extractions of the PDFs, committed so
the parse is reproducible without poppler. `pipeline/fleet_doe.py` parses them
into `web/data/fleet.json` and refuses to emit any grid whose parsed rows do
not reconcile to the PDF's own per-fuel subtotals.

An earlier extraction used a Wikipedia-derived sample (`doe_plants.csv`) before
the project found these captures. The sample was removed because Wikipedia is not a
primary source for this project.

## DOE Power Development Plan 2023-2050 (peak demand forecast)

The primary source is the Philippine Department of Energy's "Power Development
Plan 2023-2050," Table 28, "Peak Demand Forecast (2021-2050) in MW," per grid
(Luzon, Visayas, Mindanao, Philippines). doe.gov.ph returns 403 to non-PH
requests, so the file is the Internet Archive's capture of the DOE's own URL.

| File | As of | DOE URL | Wayback capture |
|---|---|---|---|
| pdp_2023-2050.txt | PDP 2023-2050 | doe.gov.ph/sites/default/files/pdf/electric_power/development_plans/Power%20Development%20Plan%202023-2050.pdf | https://web.archive.org/web/20250423153601/https://doe.gov.ph/sites/default/files/pdf/electric_power/development_plans/Power%20Development%20Plan%202023-2050.pdf |

Only the `pdftotext -layout` extraction is committed (the 4 MB PDF is
re-fetchable from the pinned Wayback capture above). `pipeline/pdp_demand.py`
parses Table 28 into `web/data/demand_path.json` and refuses any year whose
three grid values do not reconcile to the plan's own Philippines total within
2 MW. Forecast records name DOE as the owner and state the plan and horizon. The
2021 and 2022 rows are the plan's stated actuals.
