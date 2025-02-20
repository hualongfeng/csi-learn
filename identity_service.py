import logging
from csi_pb2 import GetPluginInfoResponse, GetPluginCapabilitiesResponse, PluginCapability, ProbeResponse
from csi_pb2_grpc import IdentityServicer

logger = logging.getLogger('CSIPlugin')

class IdentityService(IdentityServicer):
    def __init__(self, drivername):
        self.drivername = drivername

    def GetPluginInfo(self, request, context):
        logger.info("GetPluginInfo called")
        return GetPluginInfoResponse(name=self.drivername, vendor_version="v0.1")

    def GetPluginCapabilities(self, request, context):
        logger.info("GetPluginCapabilities called")
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
        return ProbeResponse(ready={'value': True})