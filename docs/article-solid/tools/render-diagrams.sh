#!/usr/bin/env bash
# Renderiza todos os .puml em diagrams/ para PNG em diagrams/png/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTICLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JAR="$SCRIPT_DIR/plantuml.jar"
SRC_DIR="$ARTICLE_DIR/diagrams"
OUT_DIR="$SRC_DIR/png"

mkdir -p "$OUT_DIR"

for puml in "$SRC_DIR"/*.puml; do
  [ -e "$puml" ] || continue
  echo "Rendering: $puml"
  java -jar "$JAR" -tpng -o "$OUT_DIR" "$puml"
done

echo "Done. PNGs em: $OUT_DIR"
