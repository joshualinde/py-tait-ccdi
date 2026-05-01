"""
Tait TM8100/TM8200 CCDI Protocol Library
Compatible with MicroPython and CPython (Raspberry Pi)
"""

import time
import sys

class TaitCCDI:
    def __init__(self, uart, debug=False):
        """
        uart: MicroPython machine.UART object or a file-like object with write/read
              (e.g. serial.Serial on CPython/RPi)
        """
        self.uart = uart
        self.debug = debug
        self._buffer = bytearray()

    def _log(self, msg):
        if self.debug:
            print(f"[CCDI] {msg}", file=sys.stderr)

    def _calc_checksum(self, data: bytes) -> str:
        """Calculate CCDI 8-bit checksum (two's complement)"""
        checksum = 0
        for b in data:
            checksum = (checksum + b) & 0xFF
        checksum = (~checksum + 1) & 0xFF  # two's complement
        return f"{checksum:02X}"

    def _send_command(self, ident: str, parameters: str = "") -> bool:
        """Send a CCDI command and wait for prompt '.' """
        size = f"{len(parameters):02X}"
        payload = f"{ident}{size}{parameters}".encode('ascii')
        checksum = self._calc_checksum(payload)
        packet = f"{ident}{size}{parameters}{checksum}\r".encode('ascii')

        self._log(f"Sending: {packet}")
        self.uart.write(packet)

        # Wait for prompt '.'
        return self._wait_for_prompt(timeout=2.0)

    def _wait_for_prompt(self, timeout=2.0) -> bool:
        """Wait for the '.' prompt that indicates command acceptance"""
        start = time.time()
        while time.time() - start < timeout:
            if self.uart.any():
                data = self.uart.read(self.uart.any())
                self._buffer.extend(data)
                if b'.' in self._buffer:
                    self._log("Received prompt '.'")
                    # Clean buffer up to prompt
                    idx = self._buffer.find(b'.')
                    self._buffer = self._buffer[idx+1:]
                    return True
            time.sleep(0.05)
        self._log("Timeout waiting for prompt")
        return False

    def _read_response(self, timeout=5.0) -> bytes:
        """Read unsolicited or solicited responses"""
        start = time.time()
        while time.time() - start < timeout:
            if self.uart.any():
                data = self.uart.read(self.uart.any())
                self._buffer.extend(data)
            if self._buffer:
                # For now return everything (you can parse specific messages later)
                resp = bytes(self._buffer)
                self._buffer.clear()
                return resp
            time.sleep(0.05)
        return b''

    # ====================== Public API ======================

    def go_to_channel(self, zone: int, channel: int) -> bool:
        """Change to a specific zone and channel (conventional mode)"""
        zone_str = f"{zone:02X}"
        chan_str = f"{channel:02X}"  # up to 99? Check manual for range
        params = zone_str + chan_str
        return self._send_command('g', params)

    def send_sdm(self, message: str, lead_in_delay_ms: int = 100, data_id: str = "00000000") -> bool:
        """Send a Short Data Message (SDM)"""
        # Lead-in delay in 10ms units? Manual says two hex chars.
        delay_hex = f"{lead_in_delay_ms // 10:02X}"   # e.g. 100ms -> 0A
        params = f"{delay_hex}{data_id}{message}"
        return self._send_command('s', params)

    def send_adaptable_sdm(self, message: str) -> bool:
        """Send Adaptable SDM (recommended for most uses)"""
        return self._send_command('a', message)

    def transparent_mode(self, escape_char: str = "z") -> bool:
        """Enter Transparent mode (FFSK/THSD modem mode)"""
        return self._send_command('t', escape_char)

    def function(self, func: int, subfunc: int = 0, qualifier: str = "") -> bool:
        """General FUNCTION command - very powerful"""
        sub_str = f"{subfunc:02X}" if subfunc < 100 else f"{subfunc:X}"
        params = f"{func:02X}{sub_str}{qualifier}"
        return self._send_command('f', params)

    def query(self, query_type: int = 0, data: str = "") -> bytes:
        """Query various radio information"""
        params = f"{query_type:02X}{data}"
        if self._send_command('q', params):
            return self._read_response(timeout=3.0)
        return b''

    def cancel(self, cancel_type: int = 0) -> bool:
        """Cancel current operation or delete last SDM"""
        return self._send_command('c', f"{cancel_type:02X}")

    def set_volume(self, level: int) -> bool:
        """Set volume level 0-25"""
        return self.function(0, 2, f"{level:02X}")

    def enable_progress_messages(self, enable: bool = True) -> bool:
        """Enable/disable PROGRESS messages"""
        return self.function(0, 4, "1" if enable else "0")

    def enable_sdm_output(self, enable: bool = True) -> bool:
        """Enable SDM output on reception"""
        return self.function(1, 0, "1" if enable else "0")

    def rx_audio_mute(self, mute: bool = True) -> bool:
        """Mute/unmute receiver audio"""
        return self.function(5, 0, "1" if mute else "0")

    def enter_ccr_mode(self) -> bool:
        """Switch to CCR mode"""
        return self.function(0, 0, "")

    def get_radio_versions(self):
        """Query radio software/hardware versions"""
        return self.query(0)  # QUERY type 0 often returns version info

    # ====================== Utility ======================

    def flush(self):
        """Flush input buffer"""
        while self.uart.any():
            self.uart.read(self.uart.any())
        self._buffer.clear()

    def close(self):
        if hasattr(self.uart, 'deinit'):
            self.uart.deinit()
