import os
import subprocess
import logging
from csi.csi_pb2 import (
    NodeStageVolumeResponse,
    NodeUnstageVolumeResponse,
    NodePublishVolumeResponse,
    NodeUnpublishVolumeResponse,
    NodeGetInfoResponse,
    NodeGetCapabilitiesResponse,
    NodeGetVolumeStatsResponse,
    VolumeUsage,
    VolumeCondition,
    Topology,
    NodeServiceCapability
)
from csi.csi_pb2_grpc import NodeServicer

logger = logging.getLogger('CSIPlugin')

class NodeService(NodeServicer):
    def __init__(self, nodeid):
        self.nodeid = nodeid

    def NodeStageVolume(self, request, context):
        logger.info(f"NodeStageVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id
        staging_target_path = request.staging_target_path
        src_path = request.volume_context["path"]

        # Check if the source path exists
        if not os.path.exists(src_path):
            logger.error(f"HostPath directory {src_path} does not exist")
            context.abort(grpc.StatusCode.NOT_FOUND, f"HostPath directory {src_path} does not exist")

        # HostPath 通常无需额外操作（如格式化），直接返回成功
        return NodeStageVolumeResponse()

    def NodeUnstageVolume(self, request, context):
        logger.info(f"NodeUnstageVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id
        staging_target_path = request.staging_target_path

        try:
            # 如果存在全局挂载点则卸载
            if os.path.ismount(staging_target_path):
                subprocess.run(["umount", staging_target_path], check=True)
                logger.info(f"Unmounted staging path: {staging_target_path}")

            # 删除临时目录
            if os.path.exists(staging_target_path):
                os.rmdir(staging_target_path)
                logger.info(f"Removed staging directory: {staging_target_path}")

            return NodeUnstageVolumeResponse()
        except subprocess.CalledProcessError as e:
            logger.error(f"Unmount failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Unmount failed: {e}")
        except Exception as e:
            logger.error(f"An error occurred while unstaging volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while unstaging volume {volume_id}: {e}")

    def NodePublishVolume(self, request, context):
        logger.info(f"NodePublishVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id
        target_path = request.target_path
        staging_target_path = request.staging_target_path
        src_path = request.volume_context["path"]

        try:
            # Check if the staging target path exists
            if not os.path.exists(staging_target_path):
                logger.error(f"Staging target path {staging_target_path} does not exist")
                context.abort(grpc.StatusCode.NOT_FOUND, f"Staging target path {staging_target_path} does not exist")

            # Create the directory for the target path if it does not exist
            os.makedirs(target_path, exist_ok=True)

            # Perform bind mount: mount the host path directory to the pod path
            subprocess.run(["mount", "--bind", src_path, target_path], check=True)
            logger.info(f"Mounted {src_path} to {target_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mount {src_path} to {target_path}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to mount {src_path} to {target_path}: {e}")
        except Exception as e:
            logger.error(f"An error occurred while publishing volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while publishing volume {volume_id}: {e}")

        return NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request, context):
        logger.info(f"NodeUnpublishVolume called for volume: {request.volume_id}")
        volume_id = request.volume_id
        target_path = request.target_path

        try:
            # 卸载 Pod 挂载点
            if os.path.ismount(target_path):
                subprocess.run(["umount", target_path], check=True)
                logger.info(f"Unmounted pod path: {target_path}")

            # 删除空目录（Kubernetes 预期行为）
            if os.path.exists(target_path):
                os.rmdir(target_path)
                logger.info(f"Removed pod mount directory: {target_path}")

            return NodeUnpublishVolumeResponse()
        except subprocess.CalledProcessError as e:
            logger.error(f"Unmount failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Unmount failed: {e}")
        except Exception as e:
            logger.error(f"An error occurred while unpublishing volume {volume_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"An error occurred while unpublishing volume {volume_id}: {e}")

    def NodeGetCapabilities(self, request, context):
        logger.info("NodeGetCapabilities called")
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
        logger.info("NodeGetInfo called")
        return NodeGetInfoResponse(
            node_id=self.nodeid,  # 保持使用 nodeid
        )

    def NodeGetVolumeStats(self, request, context):
        logger.info(f"NodeGetVolumeStats called for volume path: {request.volume_path}")
        path = request.volume_path  # 例如 /data/hostpath-vol1

        if not os.path.exists(path):
            logger.error(f"Path {path} not found")
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
            logger.error(f"Failed to get stats for path {path}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get stats: {str(e)}")
            return NodeGetVolumeStatsResponse()