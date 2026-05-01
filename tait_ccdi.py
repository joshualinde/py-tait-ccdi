"""
Tait TM8100/TM8200 CCDI Protocol Library - Full Featured
Supports MicroPython and CPython (Raspberry Pi with pyserial)
"""

import time
import sys
import asyncio
from collections import namedtuple, defaultdict

class TaitCCDI:
    def __init__(self, uart, debug=False):
        self.uart = uart
        self.debug = debug
        self._buffer = bytearray()
        self.current_zone = 0
        self.current_channel = 0
        self.channel_map = {}  # {name: (zone, chan)}
        self._message_handlers = defaultdict(list)

    def _log(self, msg):
        if self.debug:
            print(f"[CCDI] {msg}", file=sys.stderr)

    def _calc_checksum(self, data: bytes) -> str:
        checksum = sum(data) & 0xFF
        checksum = (~checksum + 1) & 0xFF
        return f"{checksum:02X}"

    def _send_command(self, ident: str, parameters: str = "", timeout=2.5) -> bool:
        size = f"{len(parameters):02X}"
        payload = f"{ident}{size}{parameters}".encode('ascii')
        checksum = self._calc_checksum(payload)
        packet = f"{ident}{size}{parameters}{checksum}\r".encode('ascii')

        self._log(f"TX: {packet.decode('ascii', errors='replace')}")
        self.uart.write(packet)
        return self._wait_for_prompt(timeout)

    def _wait_for_prompt(self, timeout=2.5) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if hasattr(self.uart, 'any') and self.uart.any():
                data = self.uart.read(self.uart.any() or 64)
                self._buffer.extend(data)
            elif hasattr(self.uart, 'in_waiting') and self.uart.in_waiting:
                data = self.uart.read(self.uart.in_waiting or 64)
                self._buffer.extend(data)

            if b'.' in self._buffer:
                idx = self._buffer.find(b'.')
                self._buffer = self._buffer[idx + 1:]
                self._log("Command accepted (.)")
                return True
            time.sleep(0.01)
        self._log("Timeout waiting for '.'")
        return False

    def _read_line(self, timeout=4.0) -> bytes:
        start = time.time()
        while time.time() - start < timeout:
            if self.uart.any() if hasattr(self.uart, 'any') else self.uart.in_waiting:
                data = self.uart.read(64)
                if data:
                    self._buffer.extend(data)
            if b'\r' in self._buffer:
                idx = self._buffer.find(b'\r')
                line = bytes(self._buffer[:idx])
                self._buffer = self._buffer[idx + 1:]
                return line
            time.sleep(0.01)
        return bytes(self._buffer) if self._buffer else b''

    def flush(self):
        while self.uart.any() if hasattr(self.uart, 'any') else self.uart.in_waiting:
            self.uart.read(64)
        self._buffer.clear()

    # ====================== BASIC COMMANDS ======================

    def go_to_channel(self, zone: int, channel: int) -> bool:
        params = f"{zone:02X}{channel:02X}"
        success = self._send_command('g', params)
        if success:
            self.current_zone = zone
            self.current_channel = channel
        return success

    def send_sdm(self, message: str, lead_in_ms: int = 100) -> bool:
        delay = f"{lead_in_ms // 10:02X}"
        params = f"{delay}00000000{message}"
        return self._send_command('s', params)

    def send_adaptable_sdm(self, message: str) -> bool:
        return self._send_command('a', message)

    def transparent_mode(self, escape_char: str = "z") -> bool:
        return self._send_command('t', escape_char)

    def cancel(self, cancel_type: int = 0) -> bool:
        return self._send_command('c', f"{cancel_type:02X}")

    # ====================== FUNCTION WRAPPERS ======================

    def function(self, func: int, sub: int = 0, qual: str = "") -> bool:
        params = f"{func:02X}{sub:02X}{qual}"
        return self._send_command('f', params)

    def set_volume(self, level: int) -> bool:           # 0-25
        return self.function(0, 2, f"{level:02X}")

    def enable_progress(self, enable=True):
        return self.function(0, 4, "1" if enable else "0")

    def enable_sdm_output(self, enable=True):
        return self.function(1, 0, "1" if enable else "0")

    def set_emergency(self, mode: int):                 # 0=normal, 1=stealth, 2=off
        return self.function(2, 2, str(mode))

    def monitor(self, enable=True):
        return self.function(8, 0, "1" if enable else "0")

    def mute_rx(self, mute=True):
        return self.function(5, 0, "1" if mute else "0")

    def enter_ccr_mode(self):
        return self.function(0, 0)

    # ====================== QUERY ======================

    def query(self, qtype: int = 0, extra: str = "") -> bytes:
        params = f"{qtype:02X}{extra}"
        if self._send_command('q', params, timeout=3.0):
            return self._read_line(timeout=3.0)
        return b''

    def get_radio_versions(self):
        """Returns RADIO_VERSIONS message"""
        return self.query(0)

    # ====================== MESSAGE PARSING ======================

    def parse_message(self, raw: bytes) -> dict:
        if not raw:
            return {"type": "empty"}
        try:
            msg = raw.decode('ascii', errors='replace').strip()
        except:
            msg = raw.hex()

        result = {"raw": msg, "type": "unknown"}

        if msg.startswith('r'):          # RING
            result["type"] = "ring"
        elif msg.startswith('p'):        # PROGRESS
            result["type"] = "progress"
        elif msg.startswith('e'):        # ERROR
            result["type"] = "error"
        elif msg.startswith('v'):        # RADIO_VERSIONS
            result["type"] = "versions"
        elif msg.startswith('j'):        # CCTM_QUERY_RESULTS
            result["type"] = "query_result"

        self._log(f"Parsed {result['type']}: {msg[:80]}")
        return result

    def read_message(self, timeout=3.0) -> dict:
        line = self._read_line(timeout)
        return self.parse_message(line)

    def poll_messages(self, max_messages=10, delay=0.2):
        messages = []
        for _ in range(max_messages):
            msg = self.read_message(timeout=0.5)
            if msg["type"] != "empty":
                messages.append(msg)
            else:
                break
            time.sleep(delay)
        return messages

    # ====================== CHANNEL MANAGEMENT ======================

    def add_channel(self, name: str, zone: int, channel: int):
        self.channel_map[name.lower()] = (zone, channel)

    def go_to_named_channel(self, name: str) -> bool:
        if name.lower() in self.channel_map:
            zone, chan = self.channel_map[name.lower()]
            return self.go_to_channel(zone, chan)
        self._log(f"Channel {name} not found")
        return False

    # ====================== HIGH-LEVEL ======================

    def setup_for_remote_control(self):
        self.enable_progress(True)
        self.enable_sdm_output(True)
        self.mute_rx(False)
        self.set_volume(18)
        self._log("Radio configured for remote control")

    def send_text(self, text: str, retries=3) -> bool:
        for i in range(retries):
            if self.send_adaptable_sdm(text):
                self._log(f"Text sent: {text}")
                return True
            time.sleep(0.6)
        return False

    # ====================== ASYNC SUPPORT ======================

    async def async_read_message(self, timeout=3.0):
        """Async version of read_message"""
        start = time.time()
        while time.time() - start < timeout:
            if self.uart.any() if hasattr(self.uart, 'any') else getattr(self.uart, 'in_waiting', 0):
                data = self.uart.read(64)
                if data:
                    self._buffer.extend(data)
            if b'\r' in self._buffer:
                idx = self._buffer.find(b'\r')
                line = bytes(self._buffer[:idx])
                self._buffer = self._buffer[idx + 1:]
                return self.parse_message(line)
            await asyncio.sleep(0.01)
        return {"type": "timeout"}

    async def async_poll(self, duration=10.0):
        messages = []
        start = time.time()
        while time.time() - start < duration:
            msg = await self.async_read_message(timeout=0.5)
            if msg["type"] != "timeout":
                messages.append(msg)
            await asyncio.sleep(0.1)
        return messages

    def close(self):
        self.flush()
        if hasattr(self.uart, 'deinit'):
            self.uart.deinit()


# ====================== FACTORY ======================

def create_ccdi(uart, debug=False):
    """uart can be MicroPython UART or pyserial Serial"""
    return TaitCCDI(uart, debug=debug)
