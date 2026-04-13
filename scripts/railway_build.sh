#!/usr/bin/env bash
# Railway build command.
# Set this in Railway service settings → Build Command:
#   bash scripts/railway_build.sh

set -euo pipefail

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Install backend dependencies
pip3 install -r backend/requirements.txt
