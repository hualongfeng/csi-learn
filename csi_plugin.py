from concurrent import futures
import grpc
import logging
import os
import argparse
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
    NodeGetInfoResponse,
    NodeGetCapabilitiesResponse,
    NodeServiceCapability,
    CreateSnapshotResponse,
    Snapshot,
    ListVolumesResponse,
    ControllerGetVolumeResponse,
    VolumeCondition,
    ControllerServiceCapability,
    ControllerGetCapabilitiesResponse,
    ControllerExpandVolumeResponse,
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

# Parse command line arguments
parser = argparse.ArgumentParser(description='CSI Plugin')
parser.add_argument('--drivername', type=str, required=True, help='Name of the CSI driver')
parser.add_argument('--v', type=int, default=0, help='Log level verbosity')
parser.add_argument('--endpoint', type=str, required=True, help='CSI endpoint')
parser.add_argument('--nodeid', type=str, required=True, help='Node ID')
args = parser.parse_args()

class IdentityService(IdentityServicer):
    def GetPluginInfo(self, request, context):
        logging.info("GetPluginInfo called")
        return GetPluginInfoResponse(name=args.drivername, vendor_version="v0.1")

    def GetPluginCapabilities(self, request, context):
        logging.info("GetPluginCapabilities called")
        return GetPluginCapabilitiesResponse(
            capabilities=[PluginCapability(service=PluginCapability.Service(type=PluginCapability.Service.CONTROLLER_SERVICE))]
        )

    def Probe(self, request, context):
        logging.info("Probe called")
        return ProbeResponse(ready={'value': True})

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

    def ControllerGetCapabilities(self, request, context):
        logging.info("ControllerGetCapabilities called")
        return ControllerGetCapabilitiesResponse(
            capabilities=[
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.CREATE_DELETE_VOLUME
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.GET_CAPACITY
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.CREATE_DELETE_SNAPSHOT
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.EXPAND_VOLUME
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.LIST_VOLUMES
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.GET_VOLUME
                    )
                )
            ]
        )

    def CreateSnapshot(self, request, context):
        logging.info("CreateSnapshot called")
        snapshot_id = request.name
        source_volume_id = request.source_volume_id
        snapshot_path = f"/mnt/hostpath/snapshots/{snapshot_id}"
        os.makedirs(snapshot_path, exist_ok=True)
        # Simulate snapshot creation by copying the volume data
        volume_path = f"/mnt/hostpath/{source_volume_id}"
        if os.path.exists(volume_path):
            os.system(f"cp -r {volume_path}/* {snapshot_path}/")
        return CreateSnapshotResponse(snapshot=Snapshot(snapshot_id=snapshot_id, source_volume_id=source_volume_id, creation_time=None, size_bytes=0, ready_to_use=True))

    def ListVolumes(self, request, context):
        logging.info("ListVolumes called")
        volumes = []
        for volume_id in os.listdir("/mnt/hostpath"):
            volume_path = f"/mnt/hostpath/{volume_id}"
            if os.path.isdir(volume_path):
                volume_condition = VolumeCondition(abnormal=False, message="Volume is healthy")
                volume_status = ListVolumesResponse.VolumeStatus(
                    published_node_ids=[],
                    volume_condition=volume_condition
                )
                volumes.append(ListVolumesResponse.Entry(volume=Volume(volume_id=volume_id), status=volume_status))
        return ListVolumesResponse(entries=volumes)

    def ControllerGetVolume(self, request, context):
        logging.info("ControllerGetVolume called")
        volume_id = request.volume_id
        volume_path = f"/mnt/hostpath/{volume_id}"
        if os.path.exists(volume_path):
            volume_condition = VolumeCondition(abnormal=False, message="Volume is healthy")
            volume_status = ControllerGetVolumeResponse.VolumeStatus(
                published_node_ids=[],
                volume_condition=volume_condition
            )
            return ControllerGetVolumeResponse(volume=Volume(volume_id=volume_id), status=volume_status)
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Volume not found")

    def ControllerExpandVolume(self, request, context):
        logging.info("ControllerExpandVolume called")
        volume_id = request.volume_id
        capacity_range = request.capacity_range
        volume_path = f"/mnt/hostpath/{volume_id}"
        if os.path.exists(volume_path):
            # Simulate volume expansion by updating the capacity
            return ControllerExpandVolumeResponse(capacity_bytes=capacity_range.required_bytes)
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Volume not found")

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
        if os.path.islink(staging_target_path):
            os.unlink(staging_target_path)
        return NodeUnstageVolumeResponse()

    def NodeGetCapabilities(self, request, context):
        logging.info("NodeGetCapabilities called")
        return NodeGetCapabilitiesResponse(
            capabilities=[
                NodeServiceCapability(
                    rpc=NodeServiceCapability.RPC(
                        type=NodeServiceCapability.RPC.GET_VOLUME_STATS
                    )
                )
            ]
        )

    def NodeGetInfo(self, request, context):
        logging.info("NodeGetInfo called")
        return NodeGetInfoResponse(node_id=args.nodeid)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_IdentityServicer_to_server(IdentityService(), server)
    add_ControllerServicer_to_server(ControllerService(), server)
    add_NodeServicer_to_server(NodeService(), server)
    server.add_insecure_port(args.endpoint)
    logging.info(f"Starting CSI plugin on {args.endpoint}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()