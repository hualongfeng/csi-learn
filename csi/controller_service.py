import os
import shutil
import logging
import grpc
from csi.csi_pb2 import (
    CreateVolumeResponse,
    DeleteVolumeResponse,
    ControllerPublishVolumeResponse,
    ControllerUnpublishVolumeResponse,
    ListVolumesResponse,
    ControllerGetVolumeResponse,
    Volume,
    VolumeCondition,
    Topology,
    VolumeCapability, 
    ValidateVolumeCapabilitiesResponse,
    ControllerServiceCapability,
    ControllerGetVolumeRequest,
    ControllerGetCapabilitiesResponse
)
from csi.csi_pb2_grpc import ControllerServicer

logger = logging.getLogger('CSIPlugin')

class ControllerService(ControllerServicer):
    def __init__(self, volume_root="/mnt/hostpath"):
        self.VOLUME_ROOT = volume_root

    def ControllerGetVolume(self, request: ControllerGetVolumeRequest, context):
        logger.info(f"ControllerGetVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id

        # 1. 验证卷是否存在
        vol_path = os.path.join(self.VOLUME_ROOT, volume_id)
        if not os.path.exists(vol_path):
            logger.error(f"Volume {volume_id} not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Volume {volume_id} not found")
            return ControllerGetVolumeResponse()

        # 2. 获取文件系统统计信息
        try:
            stat = os.statvfs(vol_path)
            capacity_bytes = stat.f_blocks * stat.f_frsize  # 总容量
            used_bytes = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
        except Exception as e:
            logger.error(f"Failed to get volume stats for {volume_id}: {str(e)}")
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
        logger.info(f"ValidateVolumeCapabilities called for volume: {request.volume_id}")
        # 检查卷是否存在
        vol_id = request.volume_id
        host_path = os.path.join(self.VOLUME_ROOT, vol_id)
        if not os.path.exists(host_path):
            logger.error(f"Volume {vol_id} not found")
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
        logger.info(f"CreateVolume called for volume: {request.name}")
        volume_id = request.name
        capacity = request.capacity_range.required_bytes
        path = request.parameters.get("path", os.path.join(self.VOLUME_ROOT, volume_id))

        if os.path.exists(path):
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            return CreateVolumeResponse(volume=Volume(
                volume_id=volume_id,
                capacity_bytes=capacity,
                volume_context={"path": path}
            ))

        # Create the host path directory
        os.makedirs(path, exist_ok=True)

        return CreateVolumeResponse(volume=Volume(
            volume_id=volume_id,
            capacity_bytes=capacity,
            volume_context={"path": path}
        ))

    def DeleteVolume(self, request, context):
        logger.info(f"DeleteVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id
        volume_path = os.path.join(self.VOLUME_ROOT, volume_id)  # 使用 volume_id 构建路径

        try:
            if os.path.exists(volume_path):
                shutil.rmtree(volume_path)  # 递归删除目录
                logger.info(f"Deleted HostPath volume: {volume_path}")
            return DeleteVolumeResponse()
        except OSError as e:
            logger.error(f"Failed to delete {volume_path}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to delete {volume_path}: {e}")

    def ControllerPublishVolume(self, request, context):
        logger.info(f"ControllerPublishVolume called for volume: {request.volume_id} to node: {request.node_id}")
        volume_id = request.volume_id
        node_id = request.node_id

        # HostPath 无需实际挂载到节点，直接返回成功
        return ControllerPublishVolumeResponse(publish_context={})

    def ControllerUnpublishVolume(self, request, context):
        logger.info(f"ControllerUnpublishVolume called for volume: {request.volume_id} from node: {request.node_id}")
        volume_id = request.volume_id
        node_id = request.node_id

        # HostPath 无需物理解绑操作
        logger.info(f"ControllerUnpublishVolume: No action needed for HostPath")
        return ControllerUnpublishVolumeResponse()

    def ControllerGetCapabilities(self, request, context):
        logger.info("ControllerGetCapabilities called")
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
        logger.info("ListVolumes called")
        base_dir = self.VOLUME_ROOT
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