import asyncio
import threading
import logging

import serial
import serial.tools.list_ports
from crownstone_core.protocol.BlePackets import ControlPacket
from crownstone_core.protocol.BluenetTypes import ControlType
from crownstone_uart.topics.UartTopics import UartTopics

from crownstone_uart.core.UartEventBus import UartEventBus
from crownstone_uart.core.dataFlowManagers.Collector import Collector
from crownstone_uart.core.uart.UartParser import UartParser
from crownstone_uart.core.uart.UartReadBuffer import UartReadBuffer
from crownstone_uart.core.uart.UartTypes import UartTxType
from crownstone_uart.core.uart.UartWrapper import UartWrapper
from crownstone_uart.topics.SystemTopics import SystemTopics

_LOGGER = logging.getLogger(__name__)

class UartBridge(threading.Thread):

    def __init__(self, port, baudrate):
        self.baudrate = baudrate
        self.port = port

        self.serialController = None
        self.started = False
        self.parser = None
        self.eventId = 0

        self.running = True

        threading.Thread.__init__(self)

    def __del__(self):
        self.stop_sync()

    async def handshake(self):
        collector = Collector(timeout=0.25, topic=UartTopics.uartMessage)
        self.echo("HelloCrownstone")
        reply = await collector.receive()

        if reply is not None:
            if "string" in reply:
                return reply["string"] == "HelloCrownstone"
        return False

    def echo(self, string):
        controlPacket = ControlPacket(ControlType.UART_MESSAGE).loadString(string).getPacket()
        uartPacket = UartWrapper(UartTxType.CONTROL, controlPacket).getPacket()
        self.write_to_uart(uartPacket)

    async def starting(self):
        counter = 0
        while not self.started and counter < 2:
            counter += 0.2
            await asyncio.sleep(0.02)

    def run(self):
        self.parser = UartParser()
        self.eventId = UartEventBus.subscribe(SystemTopics.uartWriteData, self.write_to_uart)
        self.start_serial()
        self.start_reading()

    def stop_sync(self):
        # print("Stopping UartBridge")
        self.running = False
        self.parser.stop()
        UartEventBus.unsubscribe(self.eventId)

    async def stop(self):
        self.stop_sync()
        counter = 0
        while self.serialController is not None and counter < 2:
            counter += 0.1
            await asyncio.sleep(0.1)

    async def isAlive(self):
        while self.serialController is not None and self.running:
            await asyncio.sleep(0.1)

    def start_serial(self):
        # print("Initializing serial on port ", self.port, ' with baudrate ', self.baudrate)
        try:
            self.serialController = serial.Serial()
            self.serialController.port = self.port
            self.serialController.baudrate = int(self.baudrate)
            self.serialController.timeout = 0.25
            self.serialController.open()
        except OSError or serial.SerialException or KeyboardInterrupt:
            self.stop_sync()

    def start_reading(self):
        readBuffer = UartReadBuffer()
        self.started = True
        # print("Read starting on serial port.")
        try:
            while self.running:
                bytesFromSerial = self.serialController.read()
                if bytesFromSerial:
                    # clear out the entire read buffer
                    if self.serialController.in_waiting > 0:
                        additionalBytes = self.serialController.read(self.serialController.in_waiting)
                        bytesFromSerial = bytesFromSerial + additionalBytes
                    readBuffer.addByteArray(bytesFromSerial)

            # print("Cleaning up UartBridge")
        except OSError or serial.SerialException:
            _LOGGER.info("Connection to USB failed. Retrying now...")
        except KeyboardInterrupt:
            self.running = False

        # close the serial controller
        self.started = False
        self.serialController.close()
        self.serialController = None
        # remove the event listener pointing to the old connection
        UartEventBus.unsubscribe(self.eventId)

    def write_to_uart(self, data):
        if self.serialController is not None and self.started:
            self.serialController.write(data)
        else:
            self.stop_sync()