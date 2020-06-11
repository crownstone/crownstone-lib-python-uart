#!/usr/bin/env python3

"""An example that switches a Crownstone, and prints the power usage of the selected Crownstone."""

import time
from crownstone_uart import CrownstoneUart, UartEventBus, UartTopics


# This is the id of the Crownstone we will be switching
# change it to match the Crownstone Id you want to switch!
targetCrownstoneId = 8

def showNewData(data):
	global targetCrownstoneId
	if data["id"] == targetCrownstoneId:
		print("New data received!")
		print("PowerUsage of crownstone", data["id"], data["powerUsageReal"])
		print("-------------------")


uart = CrownstoneUart()

# Start up the USB bridge.
uart.initialize_usb_sync()
# you can alternatively do this async by
# await uart.initialize_usb()

# Set up event listeners
UartEventBus.subscribe(UartTopics.newDataAvailable, showNewData)

# Switch this Crownstone on and off.
switchState = True

# the try except part is just to catch a control+c, time.sleep does not appreciate being killed.
try:
	for i in range(0,100):
		if not uart.running:
			break

		if switchState:
			print("Switching Crownstone on  (iteration: ", i,")")
		else:
			print("Switching Crownstone off (iteration: ", i,")")
		uart.switch_crownstone(targetCrownstoneId, on = switchState)

		switchState = not switchState
		time.sleep(2)
except KeyboardInterrupt:
	print("\nClosing example.... Thanks for your time!")

uart.stop()
