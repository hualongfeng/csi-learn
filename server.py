from concurrent import futures
import grpc
import logging
from options import parse_args
from identity_service import IdentityService
from controller_service import ControllerService
from node_service import NodeService
from csi_pb2_grpc import (
    add_IdentityServicer_to_server,
    add_ControllerServicer_to_server,
    add_NodeServicer_to_server,
)

# Configure logging to include time, filename, and log message
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('CSIPlugin')

# Parse command line arguments
args = parse_args()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_IdentityServicer_to_server(IdentityService(args.drivername), server)
    add_ControllerServicer_to_server(ControllerService(args.volume_root), server)
    add_NodeServicer_to_server(NodeService(args.nodeid), server)
    server.add_insecure_port(args.endpoint)
    logger.info(f"Starting CSI plugin on {args.endpoint}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()