# Features Included

- Full checksum calculation (verified against manual example)
- Command prompt (.) handling
- Comprehensive FUNCTION command wrapper
- Response parsing for RING, PROGRESS, ERROR
- High-level convenience methods
- Channel state tracking
- Robust buffering and flushing
- Works on both MicroPython and CPython (pyserial)
- Full response parsing (RING, PROGRESS, ERROR, RADIO_VERSIONS, etc.)
- Channel list / zone management
- GPS/NMEA integration support
- Async version (using asyncio)

# Usage Examples

## 1. Basic Synchronous (Recommended for most RPi projects)

```python
import serial
from tait_ccdi import create_ccdi

ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
radio = create_ccdi(ser, debug=True)

radio.setup_for_remote_control()
radio.add_channel("base", zone=1, channel=5)
radio.go_to_named_channel("base")

radio.send_text("Hello from Raspberry Pi - Status OK")

# Listen for incoming calls/SDMs
for _ in range(15):
    msg = radio.read_message()
    if msg["type"] != "empty":
        print(f"[{msg['type'].upper()}] {msg['raw']}")
```

## 2. Async Version

```python
async def main():
    radio = create_ccdi(ser, debug=True)
    radio.setup_for_remote_control()

    while True:
        msg = await radio.async_read_message()
        if msg["type"] != "timeout":
            print("Received:", msg)

asyncio.run(main())
3. Channel Management
Pythonradio.add_channel("dispatch", 0, 10)
radio.add_channel("tac1", 1, 3)
radio.go_to_named_channel("tac1")
```
