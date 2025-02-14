from concurrent import futures
import grpc
import logging
import os
from csi_pb2 import (
    GetPluginInfoResponse,
    GetPluginCapabilitiesResponse,
    PluginCapability,
    ProbeResponse,
    CreateVolumeResponse,
    Volume,
    DeleteVolumeResponse,
    NodeStageVolumeResponse,
    NodeUnstageVolumeResponse,
    ControllerPublishVolumeResponse,
    ControllerUnpublishVolumeResponse,
)
from csi_pb2_grpc import (
    IdentityServicer,
    ControllerServicer,
    NodeServicer,
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

class IdentityService(IdentityServicer):
    def GetPluginInfo(self, request, context):
        logging.info("GetPluginInfo called")
        return GetPluginInfoResponse(name="hostpath.csi.k8s.io", vendor_version="v0.1")

    def GetPluginCapabilities(self, request, context):
        logging.info("GetPluginCapabilities called")
        return GetPluginCapabilitiesResponse(
            capabilities=[PluginCapability(service=PluginCapability.Service(type=PluginCapability.Service.CONTROLLER_SERVICE))]
        )

    def Probe(self, request, context):
        logging.info("Probe called")
        return ProbeResponse(ready=True)

class ControllerService(ControllerServicer):
    def CreateVolume(self, request, context):
        logging.info("CreateVolume called")
        volume_id = request.name
        volume_path = f"/mnt/hostpath/{volume_id}"
        os.makedirs(volume_path, exist_ok=True)
        return CreateVolumeResponse(volume=Volume(volume_id=volume_id, capacity_bytes=request.capacity_range.required_bytes))

    def DeleteVolume(self, request, context):
        logging.info("DeleteVolume called")
        volume_id = request.volume_id
        volume_path = f"/mnt/hostpath/{volume_id}"
        if os.path.exists(volume_path):
            os.rmdir(volume_path)
        return DeleteVolumeResponse()

    def ControllerPublishVolume(self, request, context):
        logging.info("ControllerPublishVolume called")
        return ControllerPublishVolumeResponse()

    def ControllerUnpublishVolume(self, request, context):
        logging.info("ControllerUnpublishVolume called")
        return ControllerUnpublishVolumeResponse()

class NodeService(NodeServicer):
    def NodeStageVolume(self, request, context):
        logging.info("NodeStageVolume called")
        staging_target_path = request.staging_target_path
        volume_id = request.volume_id
        volume_path = f"/mnt/hostpath/{volume_id}"
        os.symlink(volume_path, staging_target_path)
        return NodeStageVolumeResponse()

    def NodeUnstageVolume(self, request, context):
        logging.info("NodeUnstageVolume called")
        staging_target_path = request.staging_target_path
        if os.islink(staging_target_path):
            os.unlink(staging_target_path)
        return NodeUnstageVolumeResponse()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_IdentityServicer_to_server(IdentityService(), server)
    add_ControllerServicer_to_server(ControllerService(), server)
    add_NodeServicer_to_server(NodeService(), server)
    server.add_insecure_port("[::]:50051")
    logging.info("Starting CSI plugin...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()