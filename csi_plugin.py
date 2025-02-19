from concurrent import futures
import grpc
import logging
import os
import argparse
import subprocess
import shutil
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
    ListVolumesResponse,
    ControllerGetVolumeResponse,
    VolumeCondition,
    ControllerServiceCapability,
    ControllerGetCapabilitiesResponse,
    NodePublishVolumeResponse,
    NodeUnpublishVolumeResponse,
    NodeGetVolumeStatsResponse,
    VolumeUsage,
    Topology,
    VolumeCapability, 
    ValidateVolumeCapabilitiesResponse,
    ControllerServiceCapability,
    ControllerGetVolumeRequest
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
            capabilities=[
                PluginCapability(
                    service=PluginCapability.Service(
                        type=PluginCapability.Service.CONTROLLER_SERVICE
                    )
                ),
                PluginCapability(
                    service=PluginCapability.Service(
                        type=PluginCapability.Service.GROUP_CONTROLLER_SERVICE
                    )
                ),
            ]
        )

    def Probe(self, request, context):
        # logging.info("Probe called")
        return ProbeResponse(ready={'value': True})

class ControllerService(ControllerServicer):
    VOLUME_ROOT = "/mnt/hostpath"  # 假设卷存储在宿主机固定目录下

    def ControllerGetVolume(self, request: ControllerGetVolumeRequest, context):
        logging.info("ControllerGetVolume called")
        volume_id = request.volume_id

        # 1. 验证卷是否存在
        vol_path = os.path.join(self.VOLUME_ROOT, volume_id)
        if not os.path.exists(vol_path):
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Volume {volume_id} not found")
            return ControllerGetVolumeResponse()

        # 2. 获取文件系统统计信息
        try:
            stat = os.statvfs(vol_path)
            capacity_bytes = stat.f_blocks * stat.f_frsize  # 总容量
            used_bytes = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get volume stats: {str(e)}")
            return ControllerGetVolumeResponse()

        # 3. 构建拓扑信息（HostPath 卷是节点本地资源）
        topology = Topology(segments={
            "topology.hostpath/node": os.uname().nodename  # 当前节点名
        })

        # 4. 构建状态条件
        status = VolumeCondition(
            abnormal=False,  # 假设存在即表示可用
            message="Volume is available"
        )

        # 5. 构建响应
        return ControllerGetVolumeResponse(
            volume=Volume(
                capacity_bytes=capacity_bytes,
                volume_id=volume_id,
                accessible_topology=[topology],
                volume_context={
                    "path": vol_path,
                    "fs_type": "hostpath",
                    "used_bytes": str(used_bytes)
                }
            ),
            status=ControllerGetVolumeResponse.VolumeStatus(
                published_node_ids=[],
                volume_condition=status
            )
        )

    def ValidateVolumeCapabilities(self, request, context):
        logging.info("ValidateVolumeCapabilities called")
        # 检查卷是否存在
        vol_id = request.volume_id
        host_path = f"/mnt/hostpath/{vol_id}"
        if not os.path.exists(host_path):
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Volume {vol_id} not found")
            return ValidateVolumeCapabilitiesResponse()

        # 检查请求能力是否支持
        supported = True
        for cap in request.volume_capabilities:
            # HostPath 仅支持文件系统挂载
            if cap.HasField("block"):
                supported = False
                break

            # 检查访问模式
            if cap.access_mode.mode not in [
                VolumeCapability.AccessMode.SINGLE_NODE_WRITER,
                VolumeCapability.AccessMode.SINGLE_NODE_READER_ONLY
            ]:
                supported = False
                break

        return ValidateVolumeCapabilitiesResponse(
            confirmed=ValidateVolumeCapabilitiesResponse.Confirmed(
                volume_capabilities=request.volume_capabilities,
                volume_context=request.volume_context
            ) if supported else None
        )

    def CreateVolume(self, request, context):
        logging.info("CreateVolume called")
        volume_id = request.name
        capacity = request.capacity_range.required_bytes
        path = request.parameters.get("path", f"/mnt/hostpath/{volume_id}")

        # Create the host path directory
        os.makedirs(path, exist_ok=True)

        return CreateVolumeResponse(volume=Volume(
            volume_id=volume_id,
            capacity_bytes=capacity,
            volume_context={"path": path}
        ))

    def DeleteVolume(self, request, context):
        logging.info("DeleteVolume called")
        volume_path = request.volume_context["path"]  # 使用 request.volume_context["path"] 获取路径

        try:
            if os.path.exists(volume_path):
                shutil.rmtree(volume_path)  # 递归删除目录
                logging.info(f"Deleted HostPath volume: {volume_path}")
            return DeleteVolumeResponse()
        except OSError as e:
            logging.error(f"Failed to delete {volume_path}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to delete {volume_path}: {e}")

    def ControllerPublishVolume(self, request, context):
        logging.info("ControllerPublishVolume called")
        volume_id = request.volume_id
        node_id = request.node_id

        # HostPath 无需实际挂载到节点，直接返回成功
        return ControllerPublishVolumeResponse(publish_context={})

    def ControllerUnpublishVolume(self, request, context):
        logging.info("ControllerUnpublishVolume called")
        volume_id = request.volume_id
        node_id = request.node_id

        # HostPath 无需物理解绑操作
        logging.info(f"ControllerUnpublishVolume: No action needed for HostPath")
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
                        type=ControllerServiceCapability.RPC.LIST_VOLUMES
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.GET_VOLUME
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.PUBLISH_UNPUBLISH_VOLUME
                    )
                ),
                ControllerServiceCapability(
                    rpc=ControllerServiceCapability.RPC(
                        type=ControllerServiceCapability.RPC.VOLUME_CONDITION
                    )
                )
            ]
        )

    def ListVolumes(self, request, context):
        logging.info("ListVolumes called")
        base_dir = "/mnt/hostpath"
        entries = []

        # 获取所有卷（示例简化实现）
        try:
            vol_ids = [d for d in os.listdir(base_dir) 
                       if os.path.isdir(os.path.join(base_dir, d))]
        except FileNotFoundError:
            return ListVolumesResponse(entries=[], next_token="0")

        # 分页处理
        start = int(request.starting_token) if request.starting_token else 0
        max_entries = request.max_entries or 100
        end = start + max_entries

        # 构建返回条目
        for vol_id in vol_ids[start:end]:
            volume_path = os.path.join(base_dir, vol_id)
            capacity_bytes = os.statvfs(volume_path).f_blocks * os.statvfs(volume_path).f_frsize
            entries.append(ListVolumesResponse.Entry(
                volume=Volume(
                    volume_id=vol_id,
                    capacity_bytes=capacity_bytes,
                    volume_context={"path": volume_path}
                )
            ))

        return ListVolumesResponse(
            entries=entries,
            next_token=str(end) if end < len(vol_ids) else ""
        )

class NodeService(NodeServicer):
    def NodeStageVolume(self, request, context):
        logging.info("NodeStageVolume called")
        volume_id = request.volume_id
        staging_target_path = request.staging_target_path
        src_path = request.volume_context["path"]

        # Check if the source path exists
        if not os.path.exists(src_path):
            context.abort(grpc.StatusCode.NOT_FOUND, f"HostPath directory {src_path} does not exist")

        # HostPath 通常无需额外操作（如格式化），直接返回成功
        return NodeStageVolumeResponse()

    def NodeUnstageVolume(self, request, context):
        logging.info("NodeUnstageVolume called")
        volume_id = request.volume_id
        staging_target_path = request.staging_target_path

        try:
            # 如果存在全局挂载点则卸载
            if os.path.ismount(staging_target_path):
                subprocess.run(["umount", staging_target_path], check=True)
                logging.info(f"Unmounted staging path: {staging_target_path}")

            # 删除临时目录
            if os.path.exists(staging_target_path):
                os.rmdir(staging_target_path)
                logging.info(f"Removed staging directory: {staging_target_path}")

            return NodeUnstageVolumeResponse()
        except subprocess.CalledProcessError as e:
            logging.error(f"Unmount failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Unmount failed: {e}")
        except Exception as e:
            logging.error(f"An error occurred while unstaging volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while unstaging volume {volume_id}: {e}")

    def NodePublishVolume(self, request, context):
        logging.info("NodePublishVolume called")
        volume_id = request.volume_id
        target_path = request.target_path
        staging_target_path = request.staging_target_path
        src_path = request.volume_context["path"]

        try:
            # Check if the staging target path exists
            if not os.path.exists(staging_target_path):
                context.abort(grpc.StatusCode.NOT_FOUND, f"Staging target path {staging_target_path} does not exist")

            # Create the directory for the target path if it does not exist
            os.makedirs(target_path, exist_ok=True)

            # Perform bind mount: mount the host path directory to the pod path
            subprocess.run(["mount", "--bind", src_path, target_path], check=True)
            logging.info(f"Mounted {src_path} to {target_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to mount {src_path} to {target_path}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to mount {src_path} to {target_path}: {e}")
        except Exception as e:
            logging.error(f"An error occurred while publishing volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while publishing volume {volume_id}: {e}")

        return NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request, context):
        logging.info("NodeUnpublishVolume called")
        volume_id = request.volume_id
        target_path = request.target_path

        try:
            # 卸载 Pod 挂载点
            if os.path.ismount(target_path):
                subprocess.run(["umount", target_path], check=True)
                logging.info(f"Unmounted pod path: {target_path}")

            # 删除空目录（Kubernetes 预期行为）
            if os.path.exists(target_path):
                os.rmdir(target_path)
                logging.info(f"Removed pod mount directory: {target_path}")

            return NodeUnpublishVolumeResponse()
        except subprocess.CalledProcessError as e:
            logging.error(f"Unmount failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Unmount failed: {e}")
        except Exception as e:
            logging.error(f"An error occurred while unpublishing volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while unpublishing volume {volume_id}: {e}")

    def NodeGetCapabilities(self, request, context):
        logging.info("NodeGetCapabilities called")
        return NodeGetCapabilitiesResponse(
            capabilities=[
                NodeServiceCapability(
                    rpc=NodeServiceCapability.RPC(
                        type=NodeServiceCapability.RPC.STAGE_UNSTAGE_VOLUME
                    )
                ),
                NodeServiceCapability(
                    rpc=NodeServiceCapability.RPC(
                        type=NodeServiceCapability.RPC.VOLUME_CONDITION
                    )
                ),
                NodeServiceCapability(
                    rpc=NodeServiceCapability.RPC(
                        type=NodeServiceCapability.RPC.GET_VOLUME_STATS
                    )
                ),
                NodeServiceCapability(
                    rpc=NodeServiceCapability.RPC(
                        type=NodeServiceCapability.RPC.SINGLE_NODE_MULTI_WRITER
                    )
                )
            ]
        )

    def NodeGetInfo(self, request, context):
        logging.info("NodeGetInfo called")
        return NodeGetInfoResponse(
            node_id=args.nodeid,  # 保持使用 args.nodeid
        )

    def NodeGetVolumeStats(self, request, context):
        logging.info("NodeGetVolumeStats called")
        path = request.volume_path  # 例如 /data/hostpath-vol1

        if not os.path.exists(path):
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Path {path} not found")
            return NodeGetVolumeStatsResponse()

        try:
            stat = os.statvfs(path)
            total_bytes = stat.f_blocks * stat.f_frsize
            available_bytes = stat.f_bavail * stat.f_frsize
            used_bytes = total_bytes - available_bytes

            return NodeGetVolumeStatsResponse(
                usage=[
                    VolumeUsage(
                        total=total_bytes,
                        available=available_bytes,
                        used=used_bytes,
                        unit=VolumeUsage.Unit.BYTES
                    )
                ],
                volume_condition=VolumeCondition(
                    abnormal=False,
                    message="Volume is healthy"
                )
            )
        except Exception as e:
            logging.error(f"Failed to get stats for path {path}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get stats: {str(e)}")
            return NodeGetVolumeStatsResponse()

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