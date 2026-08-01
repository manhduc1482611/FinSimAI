#!/usr/bin/env python3
"""Sinh TypeScript types tự động từ các Pydantic schemas của Backend Gateway.

Nguồn:  ``apps/backend_gateway/schemas/*.py``
Đích:   ``packages/shared-types/generated/api-types.ts``

Nguyên tắc mapping (đã kiểm chứng với FastAPI 0.141 + Pydantic 2.13):

- ``Decimal``          → ``string``  — FastAPI serializes Decimal thành JSON *string*
  (đã xác minh bằng ``model_dump(mode="json")`` / ``jsonable_encoder``), KHÔNG phải number.
- ``datetime``/``date`` → ``string``  (ISO-8601 trên wire)
- ``uuid.UUID``        → ``string``
- ``EmailStr``         → ``string``
- ``int``              → ``number``
- ``float``            → ``number``
- ``bool``             → ``boolean``
- ``Literal[...]``     → union of string literals
- ``list[T]``          → ``T[]``
- ``X | None``         → ``X | null``
- ``BaseModel``        → tham chiếu interface cùng tên (định nghĩa trong cùng file)
- Field KHÔNG bắt buộc (có default) → thuộc tính optional ``field?: T | null``

Chạy:  ``python scripts/generate_ts_types.py`` (từ root workspace)
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import NoneType, UnionType
from typing import Annotated, get_args, get_origin

from pydantic import BaseModel

BACKEND_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "apps" / "backend_gateway"
OUTPUT_FILE = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "shared-types"
    / "generated"
    / "api-types.ts"
)

SCHEMA_MODULES = ["user", "news", "company", "trade", "social", "knowledge", "risk"]
INJECTED_TYPES: list[str] = []


def _type_to_ts(annotation: object, context_name: str) -> str:
    """Convert một Python type annotation thành chuỗi TypeScript tương ứng."""
    # Bỏ qua Annotated[...] metadata.
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Union / Optional
    if origin in (UnionType, __import__("typing").Union):
        parts: list[str] = []
        for arg in args:
            ts = _type_to_ts(arg, context_name)
            if ts not in parts:
                parts.append(ts)
        # "null" luôn xếp cuối cho dễ đọc.
        non_null = [p for p in parts if p != "null"]
        nulls = [p for p in parts if p == "null"]
        joined = " | ".join(non_null + nulls)
        if not non_null:
            return "null"
        return joined

    # Decimal → string (wire format, đã kiểm chứng)
    if isinstance(annotation, type) and issubclass(annotation, DecimalType):
        return "string"
    # datetime / date → string (ISO-8601)
    if isinstance(annotation, type) and issubclass(annotation, DateTimeType):
        return "string"
    # UUID → string
    if annotation is UUIDType:
        return "string"
    # str (bao gồm EmailStr, các str-subclass khác).
    # Lưu ý: pydantic EmailStr/AnyUrl/... dùng metaclass nên KHÔNG phải str-subclass
    # thực thụ (mro = [EmailStr, object]) — cần nhận diện theo tên class.
    if isinstance(annotation, type) and (
        issubclass(annotation, str)
        or annotation.__name__ in {"EmailStr", "NameEmail", "AnyUrl", "SecretStr", "SecretBytes"}
    ):
        return "string"
    if annotation is int:
        return "number"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is NoneType:
        return "null"

    # Literal["a", "b"] → "a" | "b"
    if origin is __import__("typing").Literal:
        literals: list[str] = []
        for val in args:
            if isinstance(val, str):
                literals.append(json.dumps(val))
            elif isinstance(val, bool):
                literals.append("true" if val else "false")
            elif val is None:
                literals.append("null")
            else:
                literals.append(str(val))
        return " | ".join(literals) if literals else "string"

    # list[T] / Sequence[T] → T[]
    if origin in (list, __import__("typing").List, __import__("typing").Sequence):
        if not args:
            return "unknown[]"
        return f"{_type_to_ts(args[0], context_name)}[]"

    # dict[K, V] → Record<K, V>
    if origin in (dict, __import__("typing").Dict):
        key = _type_to_ts(args[0], context_name) if args else "string"
        value = _type_to_ts(args[1], context_name) if len(args) > 1 else "unknown"
        return f"Record<{key}, {value}>"

    # Nested BaseModel → tham chiếu interface cùng tên
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__

    # Fallback an toàn: ưu tiên chọn kiểu "string" hơn là đặt any/unknown sai lệch.
    print(
        f"  [WARN] {context_name}: không nhận diện được annotation "
        f"{annotation!r} → map về `string`",
        file=sys.stderr,
    )
    return "string"


def _field_to_ts(
    field_name: str,
    field_info,
    context_name: str,
) -> str:
    base = _type_to_ts(field_info.annotation, context_name)
    optional = "?" if not field_info.is_required() else ""
    return f"  {field_name}{optional}: {base}"


def _collect_models() -> list[tuple[str, type[BaseModel]]]:
    """Import toàn bộ schema modules và thu thập các Pydantic models định nghĩa tại đó."""
    sys.path.insert(0, str(BACKEND_SCHEMAS_DIR))
    models: list[tuple[str, type[BaseModel]]] = []
    for module_name in SCHEMA_MODULES:
        module = importlib.import_module(f"schemas.{module_name}")
        for _, cls in sorted(vars(module).items(), key=lambda item: item[0]):
            if (
                isinstance(cls, type)
                and issubclass(cls, BaseModel)
                and cls.__module__ == f"schemas.{module_name}"
                and cls is not BaseModel
            ):
                models.append((module_name, cls))
    return models


def _slug(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _generate(models: list[tuple[str, type[BaseModel]]]) -> str:
    lines: list[str] = []
    lines.append("/* eslint-disable */")
    lines.append("// AUTO-GENERATED — DO NOT EDIT.")
    lines.append("// Nguồn: scripts/generate_ts_types.py (Pydantic schemas của Backend Gateway).")
    lines.append("//")
    lines.append("// QUY ƯỚC TYPE (khớp đúng wire format của FastAPI):")
    lines.append("//   - Decimal → string   (FastAPI serialize Decimal thành JSON string)")
    lines.append("//   - datetime → string  (ISO-8601)")
    lines.append("//   - uuid → string")
    lines.append("//   - Optional field (có default) → `field?: T | null`")
    lines.append("// Nếu backend đổi schema, chạy lại: `npm run generate:types` (root).")
    lines.append("")
    lines.append("export type JsonValue = string | number | boolean | null | JsonValue[]")
    lines.append("    | { [key: string]: JsonValue };")
    lines.append("")

    for module_name, model in models:
        lines.append(f"// ─── {module_name.upper()} · {_slug(model.__name__).upper()} ───")
        lines.append(f"export interface {model.__name__} {{")
        fields = list(model.model_fields.items())
        if not fields:
            lines.append("  [key: string]: JsonValue;")
        for field_name, field_info in fields:
            lines.append(_field_to_ts(field_name, field_info, model.__name__))
        lines.append("}")
        lines.append("")

    lines.append("// ─── ERROR SHAPE (FastAPI mặc định) ───")
    lines.append("export interface ApiError {")
    lines.append("  detail: string;")
    lines.append("}")
    lines.append("")

    if INJECTED_TYPES:
        lines.extend(INJECTED_TYPES)
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    # Windows console mặc định cp1252 — buộc UTF-8 để print tiếng Việt không lỗi.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    # Import chuẩn các kiểu Python cần dùng cho việc so sánh issubclass.
    global DecimalType, DateTimeType, UUIDType, json
    import json
    import uuid
    from datetime import date, datetime  # noqa: F401
    from decimal import Decimal

    DecimalType = Decimal
    DateTimeType = datetime
    UUIDType = uuid.UUID

    models = _collect_models()
    if not models:
        print("ERROR: không tìm thấy Pydantic models nào trong schemas", file=sys.stderr)
        sys.exit(1)

    content = _generate(models)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"OK: đã sinh {len(models)} interfaces → {OUTPUT_FILE}")
    for module_name, model in models:
        print(f"  - {module_name:>10}  {model.__name__}")


if __name__ == "__main__":
    main()
