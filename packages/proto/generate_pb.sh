#!/bin/bash
# Generate Python gRPC stubs from math_engine.proto
# Requires: protoc, grpcio-tools (pip install grpcio-tools)

DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR_MATH_ENGINE="$DIR/../../apps/math_engine/grpc_services"
OUT_DIR_GATEWAY="$DIR/../../apps/backend_gateway/clients/proto"

mkdir -p "$OUT_DIR_MATH_ENGINE"
mkdir -p "$OUT_DIR_GATEWAY"

python -m grpc_tools.protoc \
  -I"$DIR" \
  --python_out="$OUT_DIR_MATH_ENGINE" \
  --grpc_python_out="$OUT_DIR_MATH_ENGINE" \
  "$DIR/math_engine.proto"

python -m grpc_tools.protoc \
  -I"$DIR" \
  --python_out="$OUT_DIR_GATEWAY" \
  --grpc_python_out="$OUT_DIR_GATEWAY" \
  "$DIR/math_engine.proto"

# Auto-patch relative import bug in Python gRPC generated files
sed -i 's/import math_engine_pb2 as/from . import math_engine_pb2 as/g' "$OUT_DIR_MATH_ENGINE"/math_engine_pb2_grpc.py
sed -i 's/import math_engine_pb2 as/from . import math_engine_pb2 as/g' "$OUT_DIR_GATEWAY"/math_engine_pb2_grpc.py

echo "Generated & Patched:"
ls -1 "$OUT_DIR_MATH_ENGINE"/math_engine_pb2*.py
ls -1 "$OUT_DIR_GATEWAY"/math_engine_pb2*.py