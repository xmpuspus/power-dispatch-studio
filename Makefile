.PHONY: backfill archive data serve e2e qa clean

PY := python3

# One-time: pull the full public window (~90 days) of every dataset into data/raw/.
backfill:
	$(PY) pipeline/archive_iemop.py --backfill

# Daily incremental fetch (what .github/workflows/archive.yml runs).
archive:
	$(PY) pipeline/archive_iemop.py --daily
	$(PY) pipeline/fuelmix.py --derive --limit 3

# Bake the static data from the archive + verified constants into web/data/.
data:
	$(PY) pipeline/build_data.py

# Range-capable dev server (web/), port 8789.
serve:
	cd web && $(PY) serve.py 8789

# Behavioral e2e against the running map. make serve & first.
# Live: make e2e BASE=https://<deploy>
BASE ?= http://localhost:8789
e2e:
	zsh tests/e2e.sh $(BASE)

# QA gate: data integrity pins + banned-framing + em-dash + AI-jargon sweep.
qa:
	$(PY) tests/test_data.py
	$(PY) tests/test_lp_parity.py
	$(PY) tests/qa_gate.py

clean:
	rm -f web/data/*.json web/data/*.geojson
