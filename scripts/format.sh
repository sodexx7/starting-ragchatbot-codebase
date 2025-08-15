#!/bin/bash

# Script for automatically formatting code

set -e

echo "🎨 Formatting code..."

echo "📦 Running isort to sort imports..."
uv run isort .

echo "📝 Running Black formatter..."
uv run black .

echo "✅ Code formatting complete!"