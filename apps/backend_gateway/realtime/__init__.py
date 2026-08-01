import sys
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent)]

for entry in sys.path:
    if not entry:
        continue
    candidate = Path(entry) / "websockets" / "__init__.py"
    if not candidate.exists():
        continue
    candidate_path = candidate.resolve()
    if candidate_path.parent == Path(__file__).resolve().parent:
        continue
    if str(candidate_path.parent) not in __path__:
        __path__.append(str(candidate_path.parent))

from realtime.connection_manager import (  # noqa: I001, E402
    ClientConnection,
    ConnectionManager,
    build_message,
    connection_manager,
)
from realtime.simtime import format_sim_label, real_to_sim_epoch, sim_day_of  # noqa: I001, E402

__all__ = [
    "ClientConnection",
    "ConnectionManager",
    "build_message",
    "connection_manager",
    "format_sim_label",
    "real_to_sim_epoch",
    "sim_day_of",
]
