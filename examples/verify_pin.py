# Verify PSC / unlock (authorized use only).
# Prints attempts before/after and security memory before/after.

from sle4442_bus import SLE4442Bus
from sle4442 import SLE4442, CardLockedError

# ---- PIN CONFIG ----
PIN_IO = 1
PIN_RST = 10
PIN_CLK = 11
T_US = 10

# ---- AUTH ----
PSC = None  # e.g. b"\x12\x34\x56" (set ONLY if authorized)

# If only 1 attempt remains, keep this False unless you are 100% sure.
ALLOW_LAST_ATTEMPT = False

def main():
    if PSC is None:
        print("Set PSC in this script before running (authorized use only).")
        raise SystemExit()

    bus = SLE4442Bus(io_pin=PIN_IO, rst_pin=PIN_RST, clk_pin=PIN_CLK, t_us=T_US, debug=False)
    card = SLE4442(bus)

    atr = card.reset_and_read_atr_4b()
    print("ATR(4B):", atr.hex(" "))

    sec0 = card.read_security_memory()
    attempts0 = card.remaining_attempts()
    print("Security (before):", sec0.hex(" "), "| Remaining attempts:", attempts0)

    try:
        res = card.unlock_with_psc(
            PSC,
            refuse_if_low_attempts=not ALLOW_LAST_ATTEMPT,
            max_pulses=1000,   # keep as in your working setup
        )
        print("\nUnlock result:", "UNLOCKED" if res.unlocked else "FAILED")
        print("Attempts:", res.attempts_before, "->", res.attempts_after)
        print("Security before:", res.security_before.hex(" "))
        print("Security after :", res.security_after.hex(" "))
    except CardLockedError as e:
        print("\nUnlock refused/failed:", e)

main()