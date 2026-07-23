#!/usr/bin/env bash
# One-command runner for the Qt host/widget test net inside Linux Docker.
#
# The Qt tests (test_host_simple_mode, test_pair_review, ...) cannot execute
# reliably on this Mac — macOS provenance blocks the PySide6 offscreen plugin.
# This builds a Linux image where offscreen Qt works and runs the net there.
#
# Prereq: a container runtime. If `docker` is missing, install Docker Desktop
# for Mac (https://www.docker.com/products/docker-desktop/) and start it, OR
# `brew install colima docker && colima start`.
#
# Usage:  scripts/run_qt_tests_docker.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop for Mac (or colima) first." >&2
  exit 127
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker daemon not running. Start Docker Desktop (or 'colima start')." >&2
  exit 1
fi

echo ">> building dancelab-qt-tests (first build pulls base + apt libs, ~few min)"
docker build -f Dockerfile.test -t dancelab-qt-tests .

echo ">> running the Qt safety net (offscreen, Linux)"
docker run --rm dancelab-qt-tests
