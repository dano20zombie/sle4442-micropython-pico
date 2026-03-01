from sle4442_bus import SLE4442Bus
from sle4442 import SLE4442, CardLockedError

# -----------------------------
# Hardware configuration (Pico pins)
# -----------------------------
PIN_IO = 1
PIN_RST = 10
PIN_CLK = 11
T_US = 10

# -----------------------------
# Authorization / safety
# -----------------------------
# Set PSC only if you are authorized to access THIS card.
PSC = None  # es: b"\x12\x34\x56"

# If you have only 1 attempt remaining, keep this False unless you are 100% sure.
ALLOW_LAST_ATTEMPT = False

# Optional write demo (only if unlocked and you know what you're doing)
DO_WRITE = False
WRITE_ADDR = 0x02
WRITE_VALUE = 0x00


def hexdump(data: bytes, width: int = 16) -> None:
    """Print a classic hex dump."""
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        print(f"{i:03X}: {chunk.hex(' ')}")


def main():
    # Create low-level bus + high-level card driver
    bus = SLE4442Bus(io_pin=PIN_IO, rst_pin=PIN_RST, clk_pin=PIN_CLK, t_us=T_US, debug=False)
    card = SLE4442(bus)

    # Read ATR-like 4 bytes
    atr = card.reset_and_read_atr_4b()
    print("ATR(4B):", atr.hex(" "))

    # Read header fields (this call drains to end-of-memory to keep the card in sync)
    t, id_lo, id_hi = card.read_header16()
    print(f"Header type: 0x{t:02X} | ID: {id_hi:02X}{id_lo:02X}")

    # Read security memory and show remaining PSC attempts
    sec = card.read_security_memory()
    attempts = card.remaining_attempts()
    print("Security:", sec.hex(" "), "| Remaining PSC attempts:", attempts)

    # Optional: try PSC verification / unlock
    if PSC is not None:
        try:
            res = card.unlock_with_psc(
                PSC,
                refuse_if_low_attempts=not ALLOW_LAST_ATTEMPT,
                max_pulses=2000,
            )
            print("Unlock result:", "UNLOCKED" if res.unlocked else "FAILED")
            print("Attempts:", res.attempts_before, "->", res.attempts_after)
            print("Sec before:", res.security_before.hex(" "))
            print("Sec after :", res.security_after.hex(" "))
        except CardLockedError as e:
            print("Unlock refused/failed:", e)

    # Read a small slice (still drains internally to keep sync)
    data0 = card.read_main_memory(0, 64, drain=True)
    print("MAIN[0:64]:")
    hexdump(data0)

    # Optional: write one byte (requires unlocked state)
    if DO_WRITE:
        ok, pulses = card.write_main_memory_byte(WRITE_ADDR, WRITE_VALUE)
        print(f"WRITE addr=0x{WRITE_ADDR:02X} val=0x{WRITE_VALUE:02X} ->", "OK" if ok else "TIMEOUT", "pulses:", pulses)

        data1 = card.read_main_memory(0, 64, drain=True)
        print("MAIN after write [0:64]:")
        hexdump(data1)


main()
