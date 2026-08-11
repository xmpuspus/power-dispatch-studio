## What changes, and why

## Checks

- [ ] `pip install -r requirements.txt && make qa` passes
- [ ] `ruff check .` passes, which `make qa` does not run
- [ ] Studio change: `npm run typecheck && npm run lint && npm test -- --run`
      and `npm run build -- --base=/studio/`
- [ ] A new number in README, studio/README, methodology or for-analysts has a
      registry entry in `scripts/verify_claims.py`
- [ ] A new test joins the `qa` target in the `Makefile`
- [ ] Engine change: `make sync-engine`, and `tests/test_lp_parity.py` passes
- [ ] Studio shell change: the recorders ran, because no test touches that DOM
