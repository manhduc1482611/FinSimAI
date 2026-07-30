#!/bin/bash
# Generate Python gRPC stubs from math_engine.proto
# Requires: protoc, grpcio-tools (pip install grpcio-tools)

DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$DIR/../../apps/math_engine/grpc_services"

mkdir -p "$OUT_DIR"

python -m grpc_tools.protoc \
  -I"$DIR" \
  --python_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  "$DIR/math_engine.proto"

# Auto-patch relative import bug in Python gRPC generated files
sed -i 's/import math_engine_pb2 as/from . import math_engine_pb2 as/g' "$OUT_DIR"/math_engine_pb2_grpc.py

echo "Generated & Patched:"
ls -1 "$OUT_DIR"/math_engine_pb2*.py
