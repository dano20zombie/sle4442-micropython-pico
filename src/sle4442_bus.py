"""
sle4442_bus.py - Bit-banged 2-wire bus helpers for SLE4442-like memory cards.

This module contains only low-level pin toggling and LSB-first send/read.
Higher-level SLE4442 commands live in sle4442.py.
"""

from machine import Pin
import time


class SLE4442Bus:
    """
    Low-level bit-banged bus (CLK, RST, IO) used by SLE4442.

    IO is emulated as:
      - released/high-Z: Pin.IN
      - driven low: Pin.OUT + value(0)

    Timing is controlled by t_us (microseconds) delays around clock edges.
    """

    def __init__(self, io_pin: int, rst_pin: int, clk_pin: int, t_us: int = 10, debug: bool = False):
        self.t_us = int(t_us)
        self.debug = bool(debug)

        self.io = Pin(int(io_pin), Pin.IN)
        self.rst = Pin(int(rst_pin), Pin.OUT, value=0)
        self.clk = Pin(int(clk_pin), Pin.OUT, value=0)

    # -----------------------
    # IO helpers
    # -----------------------
    def io_release(self) -> None:
        self.io.init(Pin.IN)

    def io_low(self) -> None:
        self.io.init(Pin.OUT)
        self.io.value(0)

    # -----------------------
    # Clock helpers
    # -----------------------
    def clk_hi(self) -> None:
        self.clk.value(1)
        time.sleep_us(self.t_us)

    def clk_lo(self) -> None:
        self.clk.value(0)
        time.sleep_us(self.t_us)

    def clk_pulse(self) -> None:
        self.clk_hi()
        self.clk_lo()

    def clk_pulse_sample(self) -> int:
        self.clk_hi()
        bit = self.io.value()
        self.clk_lo()
        return bit & 1
    
    def tick_clock(self, ticks: int = 1000) -> None:
        self.io_release()
        for _ in range(int(ticks)):
            self.clk_pulse()

    # -----------------------
    # Bus conditions
    # -----------------------
    def start_condition(self) -> None:
        self.io_release()
        self.clk_hi()
        self.io_low()
        time.sleep_us(self.t_us)
        self.clk_lo()

    def stop_condition(self) -> None:
        self.io_low()
        self.clk_hi()
        self.io_release()
        time.sleep_us(self.t_us)
        self.clk_lo()

    # -----------------------
    # Bit/byte transfers (LSB-first)
    # -----------------------
    def send_bit(self, bit: int) -> None:
        if bit & 1:
            self.io_release()
        else:
            self.io_low()
        self.clk_pulse()

    def send_byte_lsb(self, b: int) -> None:
        b &= 0xFF
        for i in range(8):
            self.send_bit((b >> i) & 1)

    def read_byte_lsb(self) -> int:
        self.io_release()
        b = 0
        for i in range(8):
            b |= (self.clk_pulse_sample() & 1) << i
        return b & 0xFF

    # -----------------------
    # Card reset / sync helpers
    # -----------------------
    def break_condition(self) -> None:
        """
        "Break" sequence used to re-sync after certain reads.
        """
        self.clk.value(0)
        self.rst.value(1)
        time.sleep_us(10)
        self.rst.value(0)
        time.sleep_us(10)

    def reset_and_read_atr_4b(self) -> bytes:
        """
        Reset + read 32 bits (4 bytes) ATR-like stream, LSB-first per byte.
        """
        self.io_release()
        self.clk.value(0)

        self.rst.value(1)
        time.sleep_us(5 * self.t_us)
        self.clk_pulse()
        self.rst.value(0)
        time.sleep_us(2 * self.t_us)

        bits = [self.clk_pulse_sample() for _ in range(32)]
        self.clk_pulse()

        out = bytearray()
        for i in range(0, 32, 8):
            b = 0
            for j in range(8):
                b |= (bits[i + j] & 1) << j
            out.append(b & 0xFF)
        return bytes(out)

    def processing_wait(self, max_pulses=2000, min_pulses=260):
        """
        Clock the card until IO returns '1' during CLK high (ready).
        """
        self.io_release()
        max_pulses = int(max_pulses)
        min_pulses = int(min_pulses)

        for i in range(max_pulses):
            self.clk_hi()
            ready = (self.io.value() == 1)
            self.clk_lo()
            if i >= min_pulses and ready:
                return True
        return False
    
    def processing_wait_pulses(self, max_pulses: int = 5000, min_pulses: int = 260) -> int:
        """
        Like processing_wait(), but returns pulses used.
        Returns -1 on timeout.
        """
        self.io_release()
        max_pulses = int(max_pulses)
        min_pulses = int(min_pulses)

        for i in range(max_pulses):
            self.clk_hi()
            ready = (self.io.value() == 1)
            self.clk_lo()
            if i >= min_pulses and ready:
                return i + 1
        return -1

    # -----------------------
    # Common command helper
    # -----------------------
    def write_cmd3(self, ctrl: int, addr: int, data: int) -> None:
        """
        Send 3-byte command frame: CTRL, ADDR, DATA with start/stop.
        """
        self.start_condition()
        self.send_byte_lsb(ctrl)
        self.send_byte_lsb(addr)
        self.send_byte_lsb(data)
        self.stop_condition()
