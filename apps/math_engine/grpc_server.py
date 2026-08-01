import logging
from concurrent import futures

import grpc

from grpc_services import math_engine_pb2_grpc as pb2_grpc
from grpc_services.math_service_handler import MathEngineServiceServicer

GRPC_PORT = 50051
MAX_WORKERS = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    pb2_grpc.add_MathEngineServiceServicer_to_server(
        MathEngineServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    logger.info("MathEngine gRPC server listening on port %d", GRPC_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
