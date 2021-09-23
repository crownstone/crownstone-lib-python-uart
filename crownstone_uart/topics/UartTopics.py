
class UartTopics:

    newDataAvailable = "UART_newDataAvailable"

    uartMessage = "UART_Message" # data is dictionary: {"string": str, "data": [uint8, uint8, ...] }

    hello = "UART_hello" # Data is: UartCrownstoneHelloPacket

    log = "UART_log" # Data is UartLogPacket
    logArray = "UART_logArray" # Data is UartLogArrayPacket

    assetIdReport = "assetIdReport" # Data is an AssetIdReport class instance.
    assetTrackingReport = "assetTrackingReport" # Data is an AssetMacReport class instance.
    nearestCrownstoneTrackingUpdate = "nearestCrownstoneTrackingUpdate" # Data is a NearestCrownstoneTrackingUpdate class instance
    nearestCrownstoneTrackingTimeout = "nearestCrownstoneTrackingTimeout" # Data is a NearestCrownstoneTrackingTimeout class instance