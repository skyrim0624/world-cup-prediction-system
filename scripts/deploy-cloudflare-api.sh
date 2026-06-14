#!/usr/bin/env bash
set -euo pipefail

uv run pywrangler sync
rm -rf python_modules/backend
cp -R backend python_modules/backend
find python_modules/backend -name "__pycache__" -type d -prune -exec rm -rf {} +
npx wrangler deploy
