#!/usr/bin/env bash
set -euo pipefail

uv run pywrangler sync
rm -rf python_modules/backend
cp -R backend python_modules/backend
rm -rf python_modules/reports
if [ -f reports/model-quality-report.json ]; then
  mkdir -p python_modules/reports
  cp reports/model-quality-report.json python_modules/reports/model-quality-report.json
fi
find python_modules/backend -name "__pycache__" -type d -prune -exec rm -rf {} +
npx wrangler deploy
