"""Kiểm tra cấu hình deploy (render.yaml + file env mẫu).

Bối cảnh (#14): ``render.yaml`` từng thiếu ``INTERNAL_API_KEY``/
``BACKEND_GATEWAY_URL`` và các file ``.env*.example`` không liệt kê đủ biến nối
3 service. Test này là chốt chặn hồi quy: bắt buộc mỗi service Render khai báo
đúng các biến tối thiểu, và tài liệu env phải phản ánh chúng.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
RENDER_YAML = ROOT / "render.yaml"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_PROD_EXAMPLE = ROOT / ".env.production.example"

# Biến tối thiểu theo từng service — khớp với những gì code thực sự đọc.
REQUIRED_ENV: dict[str, set[str]] = {
    "backend-gateway": {
        "DATABASE_URL",
        "DATABASE_URL_SYNC",
        "REDIS_URL",
        "JWT_SECRET",
        "INTERNAL_API_KEY",
        "MATH_ENGINE_URL",
        "ENVIRONMENT",
        "FORWARDED_ALLOW_IPS",
    },
    "math-engine": {"INTERNAL_API_KEY", "ENVIRONMENT"},
    "ai-engine-api": {
        "REDIS_URL",
        "GEMINI_API_KEY",
        "INTERNAL_API_KEY",
        "BACKEND_GATEWAY_URL",
        "ENVIRONMENT",
    },
}


def _render_services() -> dict[str, set[str]]:
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    services: dict[str, set[str]] = {}
    for svc in data["services"]:
        keys = {var["key"] for var in svc.get("envVars", [])}
        services[svc["name"]] = keys
    return services


@pytest.mark.parametrize("service,required", sorted(REQUIRED_ENV.items()))
def test_render_service_declares_required_env(service: str, required: set[str]) -> None:
    keys = _render_services().get(service)
    assert keys is not None, f"render.yaml thiếu service {service!r}"
    missing = required - keys
    assert not missing, f"render.yaml thiếu biến cho {service!r}: {sorted(missing)}"


def test_internal_api_key_shared_across_services() -> None:
    services = _render_services()
    for name in ("backend-gateway", "math-engine", "ai-engine-api"):
        assert "INTERNAL_API_KEY" in services[name], f"{name} thiếu INTERNAL_API_KEY"


def test_production_env_example_documents_internal_services() -> None:
    text = ENV_PROD_EXAMPLE.read_text(encoding="utf-8")
    for key in ("INTERNAL_API_KEY", "MATH_ENGINE_URL", "AI_ENGINE_URL", "BACKEND_GATEWAY_URL"):
        assert key in text, f".env.production.example thiếu {key}"


def test_dev_env_example_documents_internal_services() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in ("INTERNAL_API_KEY", "MATH_ENGINE_URL", "AI_ENGINE_URL", "BACKEND_GATEWAY_URL"):
        assert key in text, f".env.example thiếu {key}"


def test_env_example_has_no_stale_grpc_reference() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "MATH_ENGINE_GRPC" not in text, "MATH_ENGINE_GRPC_* đã bỏ — dùng MATH_ENGINE_URL"
