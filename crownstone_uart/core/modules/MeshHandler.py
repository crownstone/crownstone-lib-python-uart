import time, math, asyncio
from typing import List

from crownstone_core import Conversion
from crownstone_core.Exceptions import CrownstoneException
from crownstone_core.protocol.BlePackets import ControlPacket, ControlStateSetPacket
from crownstone_core.protocol.BluenetTypes import ControlType, StateType, ResultValue
from crownstone_core.protocol.ControlPackets import ControlPacketsGenerator
from crownstone_core.protocol.MeshPackets import MeshMultiSwitchPacket, StoneMultiSwitchPacket, MeshSetStatePacket, MeshBroadcastPacket, MeshBroadcastAckedPacket

from crownstone_uart.core.containerClasses.MeshResult import MeshResult
from crownstone_uart.core.dataFlowManagers.BatchCollector import BatchCollector
from crownstone_uart.core.dataFlowManagers.Collector import Collector
from crownstone_uart.core.UartEventBus import UartEventBus
from crownstone_uart.core.uart.UartTypes import UartTxType
from crownstone_uart.core.uart.UartWrapper import UartWrapper
from crownstone_uart.topics.SystemTopics import SystemTopics


class MeshHandler:

    def __init__(self):
        pass


    def turn_crownstone_on(self, crownstoneId):
        self._switch_crownstone(crownstoneId, 255)


    def turn_crownstone_off(self, crownstoneId):
        self._switch_crownstone(crownstoneId, 0)


    def set_crownstone_switch_state(self, crownstoneId, switchState):
        """
        :param crownstoneId:
        :param switchState: 0 .. 1
        :return:
        """

        # forcibly map the input from [any .. any] to [0 .. 1]
        correctedValue = min(1, max(0, switchState))

        self._switch_crownstone(crownstoneId, correctedValue)


    def _switch_crownstone(self,crownstoneId, switchState):
        """
        :param crownstoneId:
        :param switchState: 0 .. 255
        :return:
        """

        # create a stone switch state packet to go into the multi switch
        stoneSwitchPacket = StoneMultiSwitchPacket(crownstoneId, switchState)

        # wrap it in a mesh multi switch packet
        meshMultiSwitchPacket = MeshMultiSwitchPacket([stoneSwitchPacket]).getPacket()

        # wrap that in a control packet
        controlPacket = ControlPacket(ControlType.MULTISWITCH).loadByteArray(meshMultiSwitchPacket).getPacket()

        # finally wrap it in an Uart packet
        uartPacket = UartWrapper(UartTxType.CONTROL, controlPacket).getPacket()

        # send over uart
        UartEventBus.emit(SystemTopics.uartWriteData, uartPacket)


    async def set_time(self, timestamp = None):
        if timestamp is None:
            timestamp = math.ceil(time.time())
        time_packet = ControlPacketsGenerator.getSetTimePacket(timestamp)
        await self._command_via_mesh_broadcast(time_packet.getPacket())


    async def send_no_op(self):
        no_op_packet = ControlPacket(ControlType.NO_OPERATION)
        await self._command_via_mesh_broadcast(no_op_packet.getPacket())


    async def set_ibeacon_uuid(self, crownstoneId: int, uuid: str, index: int = 0) -> MeshResult:
        """
        :param crownstoneId: int crownstoneUid, 1-255
        :param uuid:  string: "d8b094e7-569c-4bc6-8637-e11ce4221c18"
        :param index: for the normal uuid, index = 0, when alternating you also need to define 1 in a
                      followup command. Usually 0 has already been set by the setup procedure.
        :return:
        """
        statePacket = ControlStateSetPacket(StateType.IBEACON_UUID, index)
        statePacket.loadByteArray(Conversion.ibeaconUUIDString_to_reversed_uint8_array(uuid))
        return await self._set_state_via_mesh_acked(crownstoneId, statePacket.getPacket())


    async def set_ibeacon_major(self, crownstoneId: int, major: int, index: int = 0) -> MeshResult:
        """
        :param crownstoneId: int crownstoneUid, 1-255
        :param major:  int: uint16 0-65535
        :param index: for the normal uuid, index = 0, when alternating you also need to define 1 in a
                      followup command. Usually 0 has already been set by the setup procedure.
        :return:
        """
        statePacket = ControlStateSetPacket(StateType.IBEACON_MAJOR, index)
        statePacket.loadUInt16(major)
        return await self._set_state_via_mesh_acked(crownstoneId, statePacket.getPacket())


    async def set_ibeacon_minor(self, crownstoneId: int, minor: int, index: int = 0) -> MeshResult:
        """
        :param crownstoneId: int crownstoneUid, 1-255
        :param minor:  int: uint16 0-65535
        :param index: for the normal uuid, index = 0, when alternating you also need to define 1 in a
                      followup command. Usually 0 has already been set by the setup procedure.
        :return:
        """
        statePacket = ControlStateSetPacket(StateType.IBEACON_MINOR, index)
        statePacket.loadUInt16(minor)
        return await self._set_state_via_mesh_acked(crownstoneId, statePacket.getPacket())


    async def periodically_activate_ibeacon_index(self, crownstone_uid_array: List[int], index : int, interval_seconds: int, offset_seconds: int = 0) -> MeshResult:
        """
        You need to have 2 stored ibeacon payloads (state index 0 and 1) in order for this to work. This can be done by the set_ibeacon methods
        available in this class.

        Once the interval starts, it will set this ibeacon ID to be active. In order to have 2 ibeacon payloads interleaving, you have to call this method twice.
        To interleave every minute
        First,    periodically_activate_ibeacon_index, index 0, interval = 120 (2 minutes), offset = 0
        Secondly, periodically_activate_ibeacon_index, index 1, interval = 120 (2 minutes), offset = 60

        This will change the active ibeacon payload every minute:
        T        = 0.............60.............120.............180.............240
        activeId = 0.............1...............0...............1...............0
        period_0 = |------------120s-------------|--------------120s-------------|
        :param crownstone_uid_array:
        :param index:
        :param interval_seconds:
        :param offset_seconds:
        :return:
        """

        ibeaconConfigPacket = ControlPacketsGenerator.getIBeaconConfigIdPacket(index, offset_seconds, interval_seconds)
        return await self._command_via_mesh_broadcast_acked(crownstone_uid_array, ibeaconConfigPacket)


    async def stop_ibeacon_interval_and_set_index(self, crownstone_uid_array: List[int], index) -> MeshResult:
        """
        This method stops the interleaving for the specified ibeacon payload at that index.
        :param crownstone_uid_array:
        :param index:
        :return:
        """
        indexToEndWith = index
        indexToStartWith = 0
        if index == 0:
            indexToStartWith = 1

        ibeaconConfigPacketStart  = ControlPacketsGenerator.getIBeaconConfigIdPacket(indexToStartWith, 0, 0)
        ibeaconConfigPacketFinish = ControlPacketsGenerator.getIBeaconConfigIdPacket(indexToEndWith,   0, 0)

        meshResult = MeshResult(crownstone_uid_array)

        initialResult = await self._command_via_mesh_broadcast_acked(crownstone_uid_array, ibeaconConfigPacketStart)

        meshResult.merge(initialResult)
        successfulIds = meshResult.getSuccessfulIds()
        if len(successfulIds) == 0:
            return meshResult

        secondResult = await self._command_via_mesh_broadcast_acked(successfulIds, ibeaconConfigPacketFinish)
        meshResult.merge(secondResult)

        return meshResult


    async def _set_state_via_mesh_acked(self, crownstoneId: int, packet: bytearray) -> MeshResult:
        # 1:1 message to N crownstones with acks (only N = 1 supported for now)
        # flag value: 2
        corePacket    = MeshSetStatePacket(crownstoneId, packet).getPacket()
        controlPacket = ControlPacket(ControlType.MESH_COMMAND).loadByteArray(corePacket).getPacket()
        uartPacket    = UartWrapper(UartTxType.CONTROL, controlPacket).getPacket()

        resultCollector     = Collector(timeout=2,  topic=SystemTopics.resultPacket)
        individualCollector = BatchCollector(timeout=15, topic=SystemTopics.meshResultPacket)
        finalCollector      = Collector(timeout=15, topic=SystemTopics.meshResultFinalPacket)

        # send the message to the Crownstone
        UartEventBus.emit(SystemTopics.uartWriteData, uartPacket)

        # wait for the collectors to fill
        commandResultData = await resultCollector.receive()

        if commandResultData is not None:
            if commandResultData.resultCode is ResultValue.BUSY:
                await asyncio.sleep(0.2)
                return await self._set_state_via_mesh_acked(crownstoneId, packet)
            elif commandResultData.resultCode is not ResultValue.SUCCESS:
                raise CrownstoneException(commandResultData.resultCode, "Command has failed.")

        return await self._handleCollectors([crownstoneId], individualCollector, finalCollector)




    async def _command_via_mesh_broadcast(self, packet: bytearray):
        # this is only for time and noop
        # broadcast to all:
        # value: 1
        corePacket = MeshBroadcastPacket(packet).getPacket()
        controlPacket = ControlPacket(ControlType.MESH_COMMAND).loadByteArray(corePacket).getPacket()
        uartPacket = UartWrapper(UartTxType.CONTROL, controlPacket).getPacket()

        resultCollector     = Collector(timeout=2, topic=SystemTopics.resultPacket)

        # send the message to the Crownstone
        UartEventBus.emit(SystemTopics.uartWriteData, uartPacket)

        # wait for the collectors to fill
        commandResultData = await resultCollector.receive()

        if commandResultData is not None:
            if commandResultData.resultCode is ResultValue.BUSY:
                await asyncio.sleep(0.2)
                return await self._command_via_mesh_broadcast(packet)
            elif commandResultData.resultCode is not ResultValue.SUCCESS:
                raise CrownstoneException(commandResultData.resultCode, "Command has failed.")

        await asyncio.sleep(0.1)


    async def _command_via_mesh_broadcast_acked(self, crownstone_uid_array: List[int], packet: bytearray) -> MeshResult:
        # this is only for the set_iBeacon_config_id
        # broadcast to all, but retry until ID's in list have acked or timeout
        # value: 3
        corePacket    = MeshBroadcastAckedPacket(crownstone_uid_array, packet).getPacket()
        controlPacket = ControlPacket(ControlType.MESH_COMMAND).loadByteArray(corePacket).getPacket()
        uartPacket    = UartWrapper(UartTxType.CONTROL, controlPacket).getPacket()

        resultCollector     = Collector(timeout=2, topic=SystemTopics.resultPacket)
        individualCollector = BatchCollector(timeout=15, topic=SystemTopics.meshResultPacket)
        finalCollector      = Collector(timeout=15, topic=SystemTopics.meshResultFinalPacket)

        # send the message to the Crownstone
        UartEventBus.emit(SystemTopics.uartWriteData, uartPacket)

        # wait for the collectors to fill
        commandResultData = await resultCollector.receive()
        if commandResultData is not None:
            if commandResultData.resultCode is ResultValue.BUSY:
                await asyncio.sleep(0.2)
                return await self._command_via_mesh_broadcast_acked(crownstone_uid_array, packet)
            elif commandResultData.resultCode is not ResultValue.SUCCESS:
                raise CrownstoneException(commandResultData.resultCode, "Command has failed.")

        return await self._handleCollectors(crownstone_uid_array, individualCollector, finalCollector)



    async def _handleCollectors(self, crownstone_uid_array: List[int], individualCollector: BatchCollector, finalCollector: Collector) -> MeshResult:
        resultArray = {}
        for uid in crownstone_uid_array:
            resultArray[uid] = False

        # await the amount of times we have ID's to deliver the message to
        for uid in crownstone_uid_array:
            individualData = await individualCollector.receive()
            if individualData is not None:
                target_uid = individualData[0]
                if target_uid in resultArray:
                    resultArray[target_uid] = individualData[1].resultCode == ResultValue.SUCCESS
            individualCollector.clear()

        individualCollector.cleanup()

        finalData = await finalCollector.receive()

        result = MeshResult()
        result.acks = resultArray

        if finalData is not None:
            if finalData.resultCode == ResultValue.SUCCESS:
                result.success = True
            else:
                result.success = False
        else:
            result.success = False

        return result