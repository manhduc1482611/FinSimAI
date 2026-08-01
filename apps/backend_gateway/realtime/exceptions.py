import importlib.util
import sys
from pathlib import Path


def _load_external_websockets_module():
    local_dir = Path(__file__).resolve().parent
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry) / "websockets" / "__init__.py"
        if not candidate.exists():
            continue
        if candidate.resolve().parent == local_dir:
            continue
        spec = importlib.util.spec_from_file_location("_external_websockets", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
        raise ImportError(
            "Unable to locate the installed websockets package "
            "outside the local app package"
        )


_external_websockets = _load_external_websockets_module()

InvalidState = getattr(_external_websockets, "InvalidState")
ConnectionClosed = getattr(_external_websockets, "ConnectionClosed", None)

__all__ = ["InvalidState", "ConnectionClosed"]
