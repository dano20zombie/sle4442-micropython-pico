# Read full main memory dump (256 bytes) and print in 16-byte lines.
# Also prints ATR(4B), header fields, security and remaining attempts.

from sle4442_bus import SLE4442Bus
from sle4442 import SLE4442

# ---- PIN CONFIG ----
PIN_IO = 1
PIN_RST = 10
PIN_CLK = 11
T_US = 10

def hexdump(data: bytes, width: int = 16) -> None:
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        print(f"{i:02X}: {chunk.hex(' ')}")

def main():
    bus = SLE4442Bus(io_pin=PIN_IO, rst_pin=PIN_RST, clk_pin=PIN_CLK, t_us=T_US, debug=False)
    card = SLE4442(bus)

    atr = card.reset_and_read_atr_4b()
    print("ATR(4B):", atr.hex(" "))

    t, id_lo, id_hi = card.read_header16()
    print(f"Header type: 0x{t:02X} | ID: {id_hi:02X}{id_lo:02X}")

    sec = card.read_security_memory()
    attempts = card.remaining_attempts()
    print("Security:", sec.hex(" "), "| Remaining PSC attempts:", attempts)

    data = card.read_main_memory(0, 256, drain=True)
    print("\nMAIN memory dump (256 bytes):")
    hexdump(data)

main()