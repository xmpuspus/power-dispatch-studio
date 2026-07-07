#!/usr/bin/env bash
# Assemble the deploy output: the map at /, Power Dispatch Studio at /studio/.
# Vercel runs this via vercel.json (buildCommand); it also works locally:
#   bash scripts/vercel_build.sh && ls .vercel_out
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf .vercel_out
mkdir -p .vercel_out
cp -R web/. .vercel_out/
rm -f .vercel_out/serve.py

cd studio
npm ci
npm run build -- --base=/studio/
cd ..
cp -R studio/dist .vercel_out/studio
echo "assembled:"
ls .vercel_out
