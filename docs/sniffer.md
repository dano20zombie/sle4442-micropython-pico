# PIO Sniffer for SLE4442 (RP2040 / Pico / Pico W)

This sniffer passively monitors the **CLK** and **IO** lines between a reader/PCB and an **SLE4442** smartcard, and decodes the 3-byte command triplets:

- `CTRL` (command)
- `ADDR` (address)
- `DATA` (data byte)

It is meant for **debugging / educational analysis** on **hardware you own or are explicitly authorized to test**.

> ⚠️ Privacy & safety:
> Smartcard traffic may include **sensitive bytes** during authentication or security operations.

---

## What it captures

The PIO program:
1. Arms when it sees `IO = HIGH`
2. Detects `START` as `IO` falling **while `CLK` is HIGH**
3. Captures **24 bits** (3 bytes) following the START, synchronized to the clock
4. Decodes bytes as LSB-first (then bit-reversed for display)

The output is a stream of decoded triplets like:

- `CMD=30 ADDR=xx DATA=yy`
- `CMD=31 ADDR=xx DATA=yy`
- `CMD=33 ADDR=01/02/03 DATA=zz`

---

## Known limitations (why frames can be missed)

This is a best-effort sniffer. A few common causes of dropped frames:

- **USB serial printing is slow**: printing every frame can overflow the PIO RX FIFO.
  - Recommended: keep `VERBOSE=False` and rely on periodic stats.
- **Timing sensitivity**: if sampling happens too early/late during `CLK HIGH`, bits may be misread.
  - Tune `NOP_DELAY` (or equivalent sampling delay).
- **Signal integrity**: long wires, weak pull-ups, noisy ground can degrade edges.

---

## Wiring (tapping an existing reader / PCB)

### Minimum connections
- **GND (common ground)** between Pico and the target reader/PCB
- **CLK** from the target to Pico `PIN_CLK`
- **IO** from the target to Pico `PIN_IO`

Optional:
- **RST** can be tapped for additional analysis, but the provided PIO decoder uses only CLK+IO.

### Setup (3.3V system)
If your PCB/reader and card operate at **3.3V**, you can connect **directly** to:
- `CLK`, `IO`, (optional `RST`)
as long as you share **GND**.

### If the target system is 5V
If the reader/PCB uses **5V signalling**, you **must not** connect 5V directly to RP2040 GPIO.

Recommended options:
- **Level shifter** (MOSFET-based or dedicated IC) for `IO` and `CLK` lines
- At minimum, a **proper input protection / divider** on any signal going into Pico (especially `CLK`)
- Keep in mind `IO` is bidirectional/open-drain style on many setups: level shifting must respect that behavior.

---

## Stability notes

In my wiring (3.3V):
- Added a **1 kΩ series resistor** on **IO / CLK ** between connectors and the Raspberry/Pico

These measures generally help with:
- edge ringing / overshoot

---

## Sniffer configuration & tuning

Typical parameters:
- `PIN_CLK`, `PIN_IO`: GPIO used for tapping
- `USE_PULLUP`: enables internal pull-up on IO (sometimes helps on slow-rising lines)
- `VERBOSE`: if `True`, prints every decoded triplet (can cause drops)
- `NOP_DELAY` / sampling delay: moves the sample point inside the `CLK HIGH` window

### How to tune sampling delay
Symptoms and fixes:
- **Unknown / random commands**: increase delay (sample later during CLK HIGH)
- **Occasional bit errors**: shorten wires, ensure solid GND, increase delay slightly
- **Many missed frames**: disable verbose printing, reduce output rate

> Note: in RP2040 PIO, delays are constants in the program.

---

## Troubleshooting checklist

If the sniffer prints nonsense or misses messages:
1. Check **GND common reference**
2. Confirm **voltage level** (3.3V vs 5V)
3. Reduce wire length, add series resistor if needed
4. Set `VERBOSE=False`
5. Adjust sampling delay
6. Consider buffering (high-impedance tap) if the reader bus is sensitive

---

## Responsible use

Use only on:
- your own PCB/reader and smartcards
- lab setups where you have explicit authorization