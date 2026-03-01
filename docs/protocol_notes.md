# Protocol notes (SLE4442)

These notes document the practical details required for a stable implementation.

## LSB-first
All transfers (command and data) are LSB-first:
- bit 0 is sent/read first
- bytes are reconstructed LSB-first

## Security / Protection memory reads
Security and protection memory are 4 bytes (32 clocks) of outgoing data.
After these 32 clocks, an additional clock is used to place IO into high-Z.

Implementation pattern:
- send 3-byte command frame
- read 4 bytes (32 clocks)
- 1 extra clock

## Main memory reads: drain-to-end is required
After a `READ MAIN` command, the card continues streaming data until end-of-memory.
If you read only a short window and then send another command, the card may still be in outgoing-data mode and will not interpret your next command correctly.

Solution:
- after reading N bytes from address A, also read/drain the remaining (256 - A - N) bytes
- then provide an extra clock pulse

The driver implements this with `drain=True`.

## Processing mode waits
Some operations require internal processing time (write, PSC/EC flows).
Depending on wiring/pull-ups/clones, the “ready” signal may be tricky.
A robust approach is:
- clock the card for a minimum amount (>= 256) before accepting IO=1 as “ready”
- optionally confirm writes with a single readback verify