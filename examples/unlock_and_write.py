# Unlock with PSC and write one byte, then verify.
# WARNING: writing requires authorization and a successful unlock.

from sle4442_bus import SLE4442Bus
from sle4442 import SLE4442, CardLockedError

# ---- PIN CONFIG ----
PIN_IO = 1
PIN_RST = 10
PIN_CLK = 11
T_US = 10

# ---- AUTH ----
PSC = None  # e.g. b"\x12\x34\x56" (authorized use only)

# If only 1 attempt remains, keep this False unless you are 100% sure.
ALLOW_LAST_ATTEMPT = False

# ---- WRITE CONFIG ----
ADDR = 0x04
VALUE = 0x03

def main():
    if PSC is None:
        raise SystemExit("Set PSC in this script before running (authorized use only).")

    bus = SLE4442Bus(io_pin=PIN_IO, rst_pin=PIN_RST, clk_pin=PIN_CLK, t_us=T_US, debug=False)
    card = SLE4442(bus)

    print("ATR(4B):", card.reset_and_read_atr_4b().hex(" "))

    # Show attempts before
    sec0 = card.read_security_memory()
    attempts0 = card.remaining_attempts()
    print("Security (before):", sec0.hex(" "), "| Remaining attempts:", attempts0)

    # Unlock
    try:
        res = card.unlock_with_psc(
            PSC,
            refuse_if_low_attempts=not ALLOW_LAST_ATTEMPT,
            max_pulses=1000,
        )
    except CardLockedError as e:
        raise SystemExit(f"Unlock refused/failed: {e}")

    print("Unlock:", "UNLOCKED" if res.unlocked else "FAILED")
    print("Attempts:", res.attempts_before, "->", res.attempts_after)
    print("Security after:", res.security_after.hex(" "))

    if not res.unlocked:
        raise SystemExit("Not unlocked; refusing to write.")

    # Read current byte (safe way)
    before = card.read_main_byte(ADDR)
    print(f"Before: MAIN[0x{ADDR:02X}] = 0x{before:02X}")

    # Write
    ok, pulses = card.write_main_memory_byte(ADDR, VALUE, max_pulses=2000, verify=True)
    print(f"Write: addr=0x{ADDR:02X} value=0x{VALUE:02X} ->", "OK" if ok else "TIMEOUT", "| pulses:", pulses)
    if not ok:
        raise SystemExit("Write timeout; stopping.")

    # Verify
    after = card.read_main_byte(ADDR)
    print(f"After : MAIN[0x{ADDR:02X}] = 0x{after:02X}")

    print("VERIFY:", "OK" if after == (VALUE & 0xFF) else "MISMATCH")

main()