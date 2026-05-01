from machine import UART, Pin
import time
from tait_ccdi import TaitCCDI

# UART on GPIO 0/1 (TX/RX) - adjust pins as needed
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=1000)

radio = TaitCCDI(uart, debug=True)

radio.flush()

# Example: Change to Zone 1, Channel 5
if radio.go_to_channel(1, 5):
    print("Channel changed successfully")

# Set volume
radio.set_volume(15)

# Send an SDM
radio.send_sdm("Hello from RPi!", lead_in_delay_ms=200)

# Read any responses
resp = radio._read_response()
print("Response:", resp.decode('ascii', errors='replace'))
