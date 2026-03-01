# sniffer_pio.py - SLE4442 command sniffer (PIO) for RP2040 (Pico / Pico W)
#
# Intended for educational / debugging use on authorized setups.
# This sniffer passively taps the CLK and IO lines between a reader/PCB and an SLE4442 card.
#
# Why frames may be missed:
# - Printing every frame over USB serial is slow -> the PIO RX FIFO can overflow.
#   Use VERBOSE=False to print only periodic stats (recommended).

from machine import Pin
import rp2
import time

# ====== PINS (GPIO numbers) ======
PIN_CLK = 2  # PIO program below is written for CLK on GPIO2
PIN_IO  = 3  # IO is read through in_base/jmp_pin

# ====== TUNING ======
# NOTE: PIO delay field must be a constant. Change NOP_DELAY and re-upload if needed.
# Range: 0..31. If you miss bits or decode weird commands, try 18..31.
NOP_DELAY = const(24)

# Internal pull-up on IO (can help with open-drain style lines; may slightly load the bus)
USE_PULLUP = True

# Print every decoded command (can cause FIFO overflow at high traffic)
VERBOSE = False

# Print periodic stats
PRINT_STATS_EVERY_MS = 1000

KNOWN = {0x30, 0x31, 0x33, 0x34, 0x38, 0x39, 0x3C}

def rev8(x: int) -> int:
    # reverse bit order in a byte (LSB-first -> MSB-first)
    x = ((x & 0xF0) >> 4) | ((x & 0x0F) << 4)
    x = ((x & 0xCC) >> 2) | ((x & 0x33) << 2)
    x = ((x & 0xAA) >> 1) | ((x & 0x55) << 1)
    return x & 0xFF


# PIO program:
# 1) Arm when IO becomes high at any time.
# 2) Scan for START: IO falling edge while CLK is high.
# 3) After START, capture 24 bits (3 bytes) synchronized to CLK (LSB-first per byte).
#
# IMPORTANT: This program assumes CLK on GPIO2 (wait(... gpio, 2)).
# Change those lines if you use a different CLK GPIO.
@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopush=True,
    push_thresh=8,
    fifo_join=rp2.PIO.JOIN_RX
)
def sniff_start_and_triplet():
    wrap_target()

    # ---- ARM: wait for IO high (not tied to CLK) ----
    wait(1, pin, 0)

    # ---- SCAN: search START = IO 1->0 during CLK HIGH ----
    label("scan")
    wait(1, gpio, 2)          # CLK high (GPIO2)

    # sample IO at start of HIGH -> store in X (0/1)
    set(x, 0)
    jmp(pin, "t0_is_1")
    jmp("t0_done")
    label("t0_is_1")
    set(x, 1)
    label("t0_done")

    wait(0, gpio, 2)          # CLK low (end of HIGH)

    # if IO is still 1 at end of HIGH: not a start, keep scanning
    jmp(pin, "scan")

    # IO is 0 at end of HIGH:
    # if t0 was 1 -> IO fell during HIGH => START detected
    set(y, 0)
    jmp(x_not_y, "do_start")

    # else IO was already low: disarm and wait for IO=1 again
    wait(1, pin, 0)
    jmp("scan")

    # ---- START found: capture 24 bits (3 bytes) ----
    label("do_start")
    set(y, 23)
    label("bitloop")
    wait(1, gpio, 2)          # CLK high

    # fixed sampling delay (0..31 cycles at SM freq)
    nop() [NOP_DELAY]

    in_(pins, 1)              # read IO (in_base)
    wait(0, gpio, 2)          # CLK low
    jmp(y_dec, "bitloop")

    # re-arm for next command
    wait(1, pin, 0)
    jmp("scan")

    wrap()


def flush_fifo(sm):
    while sm.rx_fifo():
        sm.get()


def main():
    # Configure IO pin (input). Pull-up is optional.
    io = Pin(PIN_IO, Pin.IN, Pin.PULL_UP if USE_PULLUP else None)

    # StateMachine: high instruction frequency so the NOP delay has fine resolution.
    sm = rp2.StateMachine(
        0,
        sniff_start_and_triplet,
        freq=50_000_000,
        in_base=io,
        jmp_pin=io
    )
    sm.active(1)
    flush_fifo(sm)

    print("SLE4442 PIO sniffer: detects START + captures 3 bytes (CTRL, ADDR, DATA).")
    print(f"CLK=GPIO{PIN_CLK} IO=GPIO{PIN_IO} | NOP_DELAY={NOP_DELAY} | VERBOSE={VERBOSE}")
    print("Tip: if you miss frames, set VERBOSE=False (printing is slow).")
    print()

    # Stats
    stats = {k: 0 for k in KNOWN}
    cnt33 = {1: 0, 2: 0, 3: 0}
    last_stats = time.ticks_ms()

    while True:
        # Drain as many full triplets as available
        while sm.rx_fifo() >= 3:
            b0 = sm.get() & 0xFF
            b1 = sm.get() & 0xFF
            b2 = sm.get() & 0xFF

            cmd  = rev8(b0)
            addr = rev8(b1)
            dat  = rev8(b2)

            if cmd not in KNOWN:
                continue

            stats[cmd] += 1
            
            if VERBOSE:
                print(f"CMD={cmd:02X} ADDR={addr:02X} DATA={dat:02X}")

        # Periodic stats
        now = time.ticks_ms()
        if time.ticks_diff(now, last_stats) >= PRINT_STATS_EVERY_MS:
            last_stats = now

            # Compact stats line
            base = " ".join([f"{c:02X}={stats[c]}" for c in sorted(KNOWN)])
            print(f"[STATS] {base} | 33@01={cnt33[1]} 33@02={cnt33[2]} 33@03={cnt33[3]}")

main()