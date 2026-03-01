# SLE4442 MicroPython (Raspberry Pi Pico / Pico W)

MicroPython driver + tools for **SLE4442** smartcard memory chips using a **Raspberry Pi Pico / Pico W (RP2040)**.

This repository includes:
- A stable bit-banged implementation to **read**, **verify PSC (unlock)** and **write** SLE4442 main memory
- A **PIO-based sniffer** to decode command triplets on a live CLK/IO bus

> Educational / authorized use only.  
> Do not use on systems, cards, or readers you do not own or have explicit permission to test.

---

## Features

### Driver
- Read **main memory** (up to 256 bytes)
- Read **security memory** (4 bytes)
- Read **protection memory** (4 bytes)
- PSC verify/unlock flow (3 bytes) with attempt counter handling
- Write **one byte** to main memory with completion wait + optional readback verify
- Robust sync handling:
  - Main reads can **drain-to-end** to keep the card in command mode
  - Security/protection reads use the correct **32 clocks + 1 extra clock**

### Sniffer (PIO)
- Detects START condition and captures **3-byte command triplets**: `CTRL`, `ADDR`, `DATA`
- Includes tuning knobs (sampling delay, verbosity/stats)

---

## Repository layout

```
sle4442-micropython-pico/
├─ src/
│  ├─ sle4442_bus.py      # low-level bit-bang (IO/CLK/RST)
│  ├─ sle4442.py          # high-level driver (card protocol)
│  └─ main.py             # demo / entrypoint
├─ examples/
│  ├─ read_dump.py
│  ├─ unlock_and_write.py
│  ├─ verify_pin.py
│  └─ sniffer_pio.py      # PIO sniffer (tap a PCB/reader bus)
├─ docs/
│  ├─ wiring.md           # direct-to-card wiring (no PCB)
│  ├─ sniffer.md          # sniffer wiring + tuning + limitations
│  └─ protocol_notes.md   # protocol notes
├─ README.md
└─ LICENSE
```

---

## Hardware & voltage levels

- **RP2040 GPIO is 3.3V-only (not 5V tolerant).**
- If the target card/reader bus uses **5V**, add proper **level shifting** before connecting to Pico.

Two typical setups are covered in `docs/`:
- **Direct-to-card wiring (no PCB):** `docs/wiring.md`
- **Sniffer tap on an existing PCB/reader:** `docs/sniffer.md`

---

## Deploy to Pico (Thonny)

MicroPython imports modules from `/` and `/lib`.

1. Open **Thonny → View → Files**
2. On the **Raspberry Pi Pico** side, create `/lib` if it does not exist
3. Copy:
   - `src/sle4442_bus.py` → `/lib/sle4442_bus.py`
   - `src/sle4442.py` → `/lib/sle4442.py`
   - `src/main.py` → `/main.py`
4. Run `main.py`.

To run an example:
- Copy `examples/<script>.py` to the Pico root (`/`) and run it.

---

## Configuration

Pins and timing are configured in the script you run (`main.py` or an example):

```python
PIN_IO = 1
PIN_RST = 10
PIN_CLK = 11
T_US = 10  # increase (e.g. 15–30) if signals are unstable
```

---

## Quick start (driver API)

```python
from sle4442_bus import SLE4442Bus
from sle4442 import SLE4442

bus = SLE4442Bus(io_pin=1, rst_pin=10, clk_pin=11, t_us=10)
card = SLE4442(bus)

print("SEC:", card.read_security_memory().hex(" "))
data = card.read_main_memory(0, 16, drain=True)
print("MAIN[0:16]:", data.hex(" "))
```

---

## Examples

- `examples/read_dump.py`  
  Dumps the full 256 bytes of main memory in 16-byte rows.

- `examples/verify_pin.py`  
  Performs PSC verification/unlock (authorized use only) and prints attempts before/after.

- `examples/unlock_and_write.py`  
  Unlocks (PSC) and writes one byte, then verifies by readback.

- `examples/sniffer_pio.py`  
  PIO sniffer for decoding command triplets on a live CLK/IO bus.  
  See `docs/sniffer.md` for wiring, tuning, and limitations.

---

## Notes / Troubleshooting

- **Unstable reads / random bytes**
  - Increase `T_US`
  - Use short wires and solid ground
  - For direct-to-card wiring, an external IO pull-up and series resistors can improve signal integrity (see `docs/wiring.md`)

- **Commands “stop working” after reading a small slice**
  - After `READ MAIN`, the card keeps streaming data until end-of-memory.
  - Use `read_main_memory(..., drain=True)` to keep the card in command mode.

- **Write completion timeout but data seems written**
  - Some setups do not reliably expose the BUSY/READY behavior on IO.
  - The write implementation can verify success by a single readback.

- **Sniffer drops frames**
  - Avoid printing every frame (USB serial is slow). Use stats mode.
  - Tune sampling delay and keep wires short.

---

## Responsible use

This project is intended for **educational / authorized use**:
- Use only on cards/readers you own or are explicitly authorized to test.

---

## License

MIT (see `LICENSE`)
