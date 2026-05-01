import serial
from tait_ccdi import TaitCCDI

ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
radio = TaitCCDI(ser, debug=True)

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
