#!/bin/bash

# Script for running code quality checks

set -e

echo "🔍 Running code quality checks..."

echo "📝 Running Black formatter..."
uv run black --check --diff .

echo "📦 Running isort import sorter..."
uv run isort --check-only --diff .

echo "🔧 Running Flake8 linter..."
uv run flake8 .

echo "🔍 Running MyPy type checker..."
uv run mypy backend/ main.py

echo "✅ All quality checks passed!"