"""
sle4442.py - High-level driver for SLE4442 memory smartcards.
Educational / authorized use only.
"""

from sle4442_bus import SLE4442Bus

CTRL_READ_MAIN   = 0x30
CTRL_READ_SEC    = 0x31
CTRL_WRITE_SEC   = 0x33
CTRL_READ_PROT   = 0x34
CTRL_WRITE_MAIN  = 0x38
CTRL_VERIFY_FLOW = 0x39


class SLE4442Error(Exception):
    pass


class CardLockedError(SLE4442Error):
    pass


class WriteTimeoutError(SLE4442Error):
    pass


class UnlockResult:
    def __init__(self, security_before, security_after, unlocked, attempts_before, attempts_after):
        self.security_before = security_before
        self.security_after = security_after
        self.unlocked = bool(unlocked)
        self.attempts_before = int(attempts_before)
        self.attempts_after = int(attempts_after)

    def __repr__(self):
        return ("UnlockResult(unlocked=%s, attempts=%d->%d, "
                "sec_before=%s, sec_after=%s)") % (
            self.unlocked,
            self.attempts_before, self.attempts_after,
            self.security_before.hex(" "),
            self.security_after.hex(" "),
        )


class SLE4442:
    def __init__(self, bus: SLE4442Bus):
        self.bus = bus

    @staticmethod
    def _count_attempt_bits(sec0_byte0):
        ec = sec0_byte0 & 0x07
        return ((ec >> 0) & 1) + ((ec >> 1) & 1) + ((ec >> 2) & 1)

    def reset_and_read_atr_4b(self):
        return self.bus.reset_and_read_atr_4b()

    def break_condition(self):
        self.bus.break_condition()

    # -------- READS --------
    def read_security_memory(self):
        """
        Spec-correct (datasheet):
        - send command (24 clock pulses for 3 bytes)
        - outgoing data mode: 32 clock pulses (4 bytes)
        - +1 extra pulse -> I/O goes high-Z
        Without successful PSC verification, reference bytes are forced low (0x00).
        """
        self.bus.rst.value(0)
        self.bus.write_cmd3(CTRL_READ_SEC, 0x00, 0x00)

        out = bytes(self.bus.read_byte_lsb() for _ in range(4))  # 32 clocks
        self.bus.clk_pulse()  # +1 pulse: I/O -> Z
        return out

    def read_protection_memory(self):
        """
        Same outgoing-data rule: 32 clocks + 1 extra pulse.
        """
        self.bus.rst.value(0)
        self.bus.write_cmd3(CTRL_READ_PROT, 0x00, 0x00)

        out = bytes(self.bus.read_byte_lsb() for _ in range(4))  # 32 clocks
        self.bus.clk_pulse()  # +1 pulse
        return out

    def read_main_memory(self, start_addr=0, length=256, drain=True):
        """
        Read main memory starting at start_addr.
        IMPORTANT: per datasheet, after a READ MAIN MEMORY command the card will output
        data up to the end of memory; the IFD must provide enough clocks.
        We therefore read and (optionally) drain the remaining bytes to keep the card in sync.
        """
        self.bus.rst.value(0)
        start_addr &= 0xFF
    
        total = 256 - start_addr          # bytes available until end
        want = int(length)
        if want < 0:
            want = 0
        if want > total:
            want = total

        self.bus.start_condition()
        self.bus.send_byte_lsb(CTRL_READ_MAIN)
        self.bus.send_byte_lsb(start_addr)
        self.bus.send_byte_lsb(0x00)
        self.bus.stop_condition()

        out = bytearray()
        for _ in range(want):
            out.append(self.bus.read_byte_lsb())

        if drain:
            # drain remaining bytes to reach end-of-memory output
            for _ in range(total - want):
                self.bus.read_byte_lsb()
            # extra clock (+1) mentioned in datasheet timing
            self.bus.clk_pulse()

        return bytes(out)

    def read_main_byte(self, addr: int) -> int:
        """Read a single main-memory byte safely (drains to keep sync)."""
        return self.read_main_memory(addr & 0xFF, 1, drain=True)[0]
    
    def read_one_byte_with_break(self, addr):
        # Kept for backwards compatibility; prefer read_main_byte().
        return self.read_main_byte(addr)

    def read_header16(self):
        d = self.read_main_memory(0, 16)
        t = d[4]
        id_lo, id_hi = d[6], d[7]
        return t, id_lo, id_hi

    def remaining_attempts(self):
        sec = self.read_security_memory()
        return self._count_attempt_bits(sec[0])

    # -------- PSC / UNLOCK --------
    def unlock_with_psc(self, psc3, refuse_if_low_attempts=True, max_pulses=2000):
        if not isinstance(psc3, (bytes, bytearray)) or len(psc3) != 3:
            raise ValueError("psc3 must be exactly 3 bytes")

        self.bus.rst.value(0)

        sec0 = self.read_security_memory()
        attempts0 = self._count_attempt_bits(sec0[0])

        if attempts0 == 0:
            raise CardLockedError("Card has 0 remaining PSC attempts (locked).")

        if refuse_if_low_attempts and attempts0 <= 1:
            raise CardLockedError(
                "Safety stop: remaining attempts <= 1. "
                "Set refuse_if_low_attempts=False to override."
            )

        ec = sec0[0] & 0x07
        new_ec = ec & (ec - 1)

        # 1) select attempt bit
        self.bus.write_cmd3(CTRL_VERIFY_FLOW, 0x00, new_ec)
        self.bus.processing_wait(max_pulses=max_pulses)

        # 2) write PSC compare bytes
        self.bus.write_cmd3(CTRL_WRITE_SEC, 0x01, psc3[0]); self.bus.processing_wait(max_pulses=max_pulses)
        self.bus.write_cmd3(CTRL_WRITE_SEC, 0x02, psc3[1]); self.bus.processing_wait(max_pulses=max_pulses)
        self.bus.write_cmd3(CTRL_WRITE_SEC, 0x03, psc3[2]); self.bus.processing_wait(max_pulses=max_pulses)

        # 3) (Optional) erase error counter (restore attempts)
        self.bus.write_cmd3(CTRL_VERIFY_FLOW, 0x00, 0xFF)
        self.bus.processing_wait(max_pulses=max_pulses)

        sec1 = self.read_security_memory()
        attempts1 = self._count_attempt_bits(sec1[0])

        unlocked = (sec1[1:4] == bytes(psc3))

        return UnlockResult(sec0, sec1, unlocked, attempts0, attempts1)

    # -------- WRITE --------
    def write_main_memory_byte(self, addr, data, max_pulses=5000, min_pulses=260, verify=True):
        """
        Write one byte and wait for completion.

        Strategy:
        - Send write command
        - Wait processing mode completion once (clocking the card)
        - Verify by a single readback (optional)
        """
        self.bus.rst.value(0)

        # Send write command frame
        self.bus.start_condition()
        self.bus.send_byte_lsb(CTRL_WRITE_MAIN)
        self.bus.send_byte_lsb(addr & 0xFF)
        self.bus.send_byte_lsb(data & 0xFF)
        self.bus.clk_pulse()
        self.bus.stop_condition()

        # Wait for internal programming
        pulses = self.bus.processing_wait_pulses(max_pulses=max_pulses, min_pulses=min_pulses)
        if pulses < 0:
            # Timeout -> optionally check readback once
            if verify:
                rb = self.read_main_byte(addr)
                if rb == (data & 0xFF):
                    return True, max_pulses
            return False, max_pulses

        # Single readback verify
        if verify:
            rb = self.read_main_byte(addr)
            return (rb == (data & 0xFF)), pulses

        return True, pulses

    def write_main_memory_checked(self, addr, data, max_pulses=400):
        ok, pulses = self.write_main_memory_byte(addr, data, max_pulses=max_pulses)
        if not ok:
            raise WriteTimeoutError("Write timeout at addr=0x%02X after %d pulses" % (addr & 0xFF, pulses))
        return pulses



