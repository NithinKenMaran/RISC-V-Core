# TinyTapeout QSPI PMOD Behaviour Datasheet

**Scope:** behavioural reference for the TinyTapeout QSPI PMOD as used by TinyQV-style MicroPython scripts and as relevant to a Verilog PMOD simulation model.

**Board-level composition:**

- 1 × 128 Mbit / 16 MiB QSPI flash: `25Q128JVSM` / Winbond W25Q128JV-family serial NOR flash.
- 2 × 64 Mbit / 8 MiB QSPI PSRAMs: `APS6404L-3SQR`, referred to here as RAM A and RAM B.

This document is not a replacement for the chip datasheets. It is a consolidated behavioural map of the commands and modes that matter for TinyTapeout/TinyQV-style usage.

---

## 1. Physical Interface

### 1.1 Shared QSPI bus

The PMOD exposes one shared serial/quad bus:

| Signal | Meaning |
|---|---|
| `SCK` | Serial/quad clock |
| `SD0` / `MOSI` | SPI MOSI, QSPI data bit 0 |
| `SD1` / `MISO` | SPI MISO, QSPI data bit 1 |
| `SD2` | QSPI data bit 2 |
| `SD3` | QSPI data bit 3 |
| `CS0` | Active-low chip select for flash |
| `CS1` | Active-low chip select for RAM A |
| `CS2` | Active-low chip select for RAM B |

Only one chip-select should be low at a time.

### 1.2 TinyTapeout `uio` pin mapping

| TinyTapeout pin | PMOD signal | Device role |
|---|---|---|
| `uio[0]` | `CS0` | Flash select |
| `uio[1]` | `SD0` / `MOSI` | Shared data |
| `uio[2]` | `SD1` / `MISO` | Shared data |
| `uio[3]` | `SCK` | Shared clock |
| `uio[4]` | `SD2` | Shared data |
| `uio[5]` | `SD3` | Shared data |
| `uio[6]` | `CS1` | RAM A select |
| `uio[7]` | `CS2` | RAM B select |

### 1.3 SPI vs QPI/QSPI interpretation

This board can be used in multiple signalling styles:

| Name used here | Command transfer | Address transfer | Data transfer | Typical use |
|---|---:|---:|---:|---|
| SPI / 1-1-1 | 1 bit/cycle on `SD0` | 1 bit/cycle on `SD0` | 1 bit/cycle, input on `SD1`, output on `SD0` | Power-on commands, ID commands, programming |
| SPI-to-quad / 1-4-4 | Command on `SD0`; address/data on `SD[3:0]` | 4 bits/cycle | 4 bits/cycle | Flash `0xEB` quad-I/O read setup |
| QPI / 4-4-4 | Command on `SD[3:0]` | 4 bits/cycle | 4 bits/cycle | Runtime PSRAM after `0x35` |
| Flash continuous read | No command byte; address/mode/dummy/data | 4 bits/cycle | 4 bits/cycle | Runtime instruction fetch from flash |

---

## 2. Reset / Power-On Mode Summary

### 2.1 Expected power-on state

At power-on, assume:

| Device | Expected initial state |
|---|---|
| Flash | Normal serial SPI command mode, unless it was left in continuous-read mode from an earlier transaction/reset condition. TinyQV defensively sends `0xFF` to leave continuous mode. |
| PSRAM A | Normal SPI mode |
| PSRAM B | Normal SPI mode |

### 2.2 Runtime state expected by TinyQV core

After the RP2040 init script has run:

| Device | Runtime mode expected by core |
|---|---|
| Flash | Continuous quad-I/O read mode. New flash reads can omit the `0xEB` instruction byte and begin directly with address/mode/dummy/data. |
| PSRAM A | QPI mode |
| PSRAM B | QPI mode |

For a core-level Verilog simulation, this is the useful initial condition:

```verilog
flash_continuous_mode = 1'b1;
ram_a_qpi_mode        = 1'b1;
ram_b_qpi_mode        = 1'b1;
```

---

## 3. Command and Mode Reference: Flash

Flash device: Winbond-style `25Q128JVSM` / W25Q128JV-family serial NOR flash.

### 3.1 Flash modes

| Mode | Entry | Exit | Notes |
|---|---|---|---|
| Normal SPI command mode | Power-on / reset / continuous-mode exit | `0xEB` with continuous mode bits | Commands are sent as 8 serial bits on `SD0`. |
| Quad-I/O fast read transaction | `0xEB` | CS high after transaction | Command is serial; address/mode/dummy/data use quad bus. |
| Continuous read mode | `0xEB` transaction with continuous mode byte, observed as mode `0xAA` in TinyQV scripts | Mode `0xFF` in a later read, or `0xFF` as leave-CM command | Next transaction can omit instruction byte. |
| Program/erase mode | `0x06` write-enable followed by program/erase command | Operation completes when SR1 busy bit clears | Used by RP2040 flash programming scripts, not by the core runtime. |

### 3.2 Flash command byte list

The following table combines commands observed in the TinyQV MicroPython files and commands needed to model the same chip behaviour around those operations.

| Byte | Name | Bus style | Purpose | Mode effect | Observed in TinyQV files? |
|---:|---|---|---|---|---|
| `0xFF` | Leave continuous mode / reset-like escape for CM path | SPI single-bit command | Defensively exits flash continuous read mode before setup | Leaves continuous-read mode; returns to command-based operation | Yes, `run_tinyqv.py`, `flash_prog.py` |
| `0xAB` | Release power-down / wake / electronic ID path | SPI | Wakes flash before ID/programming in one programming helper | Flash becomes responsive after wake; script waits after this | Yes, `fpga_flash_prog.py`, `test_qspi_pmod.py` |
| `0x90` | Manufacturer/device ID | SPI | Reads manufacturer/device ID after dummy/address bytes | No persistent mode change | Yes, `test_qspi_pmod.py`, `flash_prog.py`, `fpga_flash_prog.py` |
| `0x9F` | JEDEC ID | SPI | Reads JEDEC ID bytes | No persistent mode change | Yes, `test_qspi_pmod.py` |
| `0x06` | Write Enable | SPI | Sets write-enable latch before erase/program | Enables next erase/program/status-write command | Yes, `flash_prog.py`, `fpga_flash_prog.py` |
| `0x05` | Read Status Register 1 | SPI | Polls status; bit 0 is busy/WIP in scripts | No persistent mode change | Yes, `flash_prog.py`, `fpga_flash_prog.py` |
| `0x20` | Sector Erase, 4 KiB | SPI + 24-bit address | Erases one 4 KiB sector | Requires `0x06`; sets busy until complete | Yes, `flash_prog.py`, `fpga_flash_prog.py` |
| `0x02` | Page Program | SPI + 24-bit address + data | Programs up to page-sized data chunks | Requires `0x06`; sets busy until complete | Yes, `flash_prog.py`, `fpga_flash_prog.py` |
| `0x03` | Normal Read Data | SPI + 24-bit address | Reads bytes in normal serial mode | No persistent mode change | Yes, verify path in flash programming files |
| `0xEB` | Fast Read Quad I/O | 1-4-4: command serial, address/mode/dummy/data quad | Used to read flash over quad bus and enter/maintain continuous read | With mode bits set to continuous pattern, enables commandless future reads | Yes, encoded by PIO bit patterns in `run_tinyqv.py` and `test_qspi_read.py` |

### 3.3 Flash normal SPI command formats

#### `0xFF`: leave continuous read mode

```text
CS0 low
send 0xFF on SD0, MSB first
CS0 high
```

Effect used by TinyQV: flash is no longer assumed to be in continuous read mode.

#### `0xAB`: release power-down / wake

```text
CS0 low
send 0xAB on SD0, MSB first
CS0 high
optional wait
```

Observed programming helper behaviour:

```text
send 0xAB
wait approximately 1 second
continue with ID/programming commands
```

The 1 second wait is conservative software behaviour, not a required bus-cycle count for the memory interface model.

#### `0x90`: manufacturer/device ID

Common datasheet-like form:

```text
CS0 low
send 0x90
send 24 address/dummy bits, usually 0x000000
read ID bytes
CS0 high
```

Observed TinyQV variants:

```text
0x90 + 0x00 0x00 0x00, then read 2 bytes
```

and:

```text
0x90, then 2 dummy bytes, then read 3 bytes
```

A permissive behavioural model should tolerate both, because the scripts are using the command only for sanity probing.

#### `0x9F`: JEDEC ID

```text
CS0 low
send 0x9F
read 3 bytes
CS0 high
```

Typical response for a Winbond 128 Mbit part would start with manufacturer ID `0xEF`; exact following bytes depend on the specific flash variant.

#### `0x06`: write enable

```text
CS0 low
send 0x06
CS0 high
```

Effect:

```text
write_enable_latch = 1
```

#### `0x05`: read status register 1

```text
CS0 low
send 0x05
read one or more status bytes
CS0 high
```

Minimum simulation behaviour:

```text
status[0] = busy / WIP
```

The TinyQV programming scripts poll:

```python
while flash_cmd([0x05], 0, 1)[0] & 1:
    sleep(0.01)
```

So the only mandatory bit for script compatibility is bit 0.

#### `0x20`: sector erase

```text
CS0 low
send 0x20
send 24-bit address, MSB first
CS0 high
```

Expected effect in model:

```text
if write_enable_latch:
    erase 4096-byte sector containing address
    busy = 1 for some modelled interval or one transaction
    write_enable_latch = 0
```

TinyQV programming address pattern erases sector `sector` using:

```text
addr = sector * 4096
bytes sent = [0x20, sector >> 4, (sector & 0xF) << 4, 0x00]
```

#### `0x02`: page program

```text
CS0 low
send 0x02
send 24-bit address, MSB first
send data bytes
CS0 high
```

Expected effect in model:

```text
if write_enable_latch:
    flash[address + i] = flash[address + i] & data[i]
    busy = 1 for some modelled interval or one transaction
    write_enable_latch = 0
```

Real NOR flash programs bits from `1` to `0`; erased flash is `0xFF`. A practical behavioural model can either implement this bitwise-AND behaviour or simply assign bytes if only software flow is being tested. Bitwise-AND is more faithful.

TinyQV programming writes chunks up to 256 bytes after each `0x06`.

#### `0x03`: normal read

```text
CS0 low
send 0x03
send 24-bit address, MSB first
read data bytes on SD1
CS0 high
```

Used by the programming scripts to verify flash contents after programming.

### 3.4 Flash `0xEB`: Fast Read Quad I/O

This is the command that matters for putting the flash into the runtime mode used by TinyQV.

#### Command-based `0xEB` read, no continuous mode retention

Observed function name: `read_data(num_bytes)`.

```text
CS0 low
send command 0xEB serially on SD0, MSB first: 8 SPI bit-cycles
send 24-bit address over SD[3:0]: 6 quad cycles
send mode byte 0xFF over SD[3:0]: 2 quad cycles
turn bus around to input
clock 4 dummy quad cycles
read data: 2 quad cycles per byte
CS0 high
```

Mode effect:

```text
flash_continuous_mode = 0
```

#### Command-based `0xEB` read that enables/keeps continuous mode

Observed function name: `read_data_enable_cm(num_bytes)`.

```text
CS0 low
send command 0xEB serially on SD0, MSB first: 8 SPI bit-cycles
send 24-bit address over SD[3:0]: 6 quad cycles
send mode byte 0xAA over SD[3:0]: 2 quad cycles
turn bus around to input
clock 4 dummy quad cycles
read data: 2 quad cycles per byte
CS0 high
```

Mode effect:

```text
flash_continuous_mode = 1
```

Notes:

- The TinyQV PIO script does not write the literal byte `0xEB` as a Python `spi.write()` byte. It emits eight GPIO states whose `SD0` bit sequence is `11101011`, i.e. `0xEB`.
- The TinyQV script emits two packed GPIO states that decode on `SD[3:0]` to `0xA` then `0xA`, i.e. mode byte `0xAA`.
- Mode byte `0xAA` has the relevant continuous-read mode bits set for this flash-family behaviour.

#### Continuous-mode commandless flash read

Observed function name: `read_data_cm(num_bytes, exit_cm=False)`.

When `flash_continuous_mode = 1`, a new read can omit the `0xEB` instruction byte:

```text
CS0 low
send 24-bit address over SD[3:0]: 6 quad cycles
send mode byte over SD[3:0]: 2 quad cycles
turn bus around to input
clock 4 dummy quad cycles
read data: 2 quad cycles per byte
CS0 high
```

If mode byte is `0xAA`:

```text
flash_continuous_mode remains 1
```

If mode byte is `0xFF`:

```text
flash_continuous_mode becomes 0 after the transaction
```

### 3.5 Flash QSPI cycle count summary

| Transaction | Command cycles | Address cycles | Mode cycles | Dummy cycles | Data cycles |
|---|---:|---:|---:|---:|---:|
| Command `0xEB` read, normal | 8 SPI bit-cycles | 6 quad cycles | 2 quad cycles, `0xFF` | 4 quad cycles | 2 quad cycles/byte |
| Command `0xEB` read, enable CM | 8 SPI bit-cycles | 6 quad cycles | 2 quad cycles, `0xAA` | 4 quad cycles | 2 quad cycles/byte |
| Continuous-mode read | 0 | 6 quad cycles | 2 quad cycles, `0xAA` or `0xFF` | 4 quad cycles | 2 quad cycles/byte |

---

## 4. Command and Mode Reference: PSRAM

PSRAM device: AP Memory `APS6404L-3SQR`, one RAM A and one RAM B.

### 4.1 PSRAM modes

| Mode | Entry | Exit | Notes |
|---|---|---|---|
| SPI mode | Power-on / reset | `0x35` | Commands, addresses, and data are single-bit SPI unless using a special quad command. |
| QPI mode | `0x35` sent in SPI mode | `0xF5`, reset, or power cycle | Commands, addresses, and data are transferred on `SD[3:0]`. TinyQV runtime expects this mode. |

### 4.2 PSRAM command byte list

| Byte | Name | Bus style | Purpose | Mode effect | Observed in TinyQV files? |
|---:|---|---|---|---|---|
| `0x35` | Enter Quad/QPI mode | SPI command | Switches PSRAM from SPI mode to QPI mode | `ram_qpi_mode = 1` | Yes, `run_tinyqv.py` |
| `0xF5` | Exit QPI mode | QPI command | Switches PSRAM from QPI mode back to SPI mode | `ram_qpi_mode = 0` | Not observed, but useful for completeness |
| `0x9F` | Read ID | SPI, sometimes also modelled in QPI | Reads PSRAM ID bytes | No persistent mode change | Yes, `test_qspi_pmod.py` |
| `0x02` | Write | SPI in SPI mode; QPI in QPI mode | Writes data bytes to PSRAM | No persistent mode change | Yes, `test_psram.py`; also runtime QPI write expected |
| `0x03` | SPI Read | SPI | Reads data bytes in default SPI mode | No persistent mode change | Yes, `test_psram.py` |
| `0x0B` | Fast Read | QPI in TinyQV runtime model | Runtime PSRAM read after `0x35` | No persistent mode change | Expected by TinyQV-style QPI controller |
| `0xEB` | Fast Quad Read | SPI/QPI depending on mode | Alternative faster quad read command | No persistent mode change | Not directly observed in MicroPython runtime subset, but in datasheet-family command set |
| `0x38` | Quad Write | SPI/QPI depending on mode | Alternative quad write command | No persistent mode change | Not observed, but in datasheet-family command set |
| `0x66` | Reset Enable | SPI/QPI depending on mode | First half of reset sequence | Arms reset | Not observed |
| `0x99` | Reset | SPI/QPI depending on mode | Completes reset sequence after `0x66` | Returns to default state | Not observed |

### 4.3 PSRAM SPI mode formats

#### `0x35`: enter QPI mode

Used by `setup_ram()` on both RAM chips.

```text
CS1 or CS2 low
send 0x35 serially on SD0, MSB first
CS1 or CS2 high
```

Effect:

```text
selected_ram_qpi_mode = 1
```

After this point, runtime commands to that RAM should be interpreted as QPI commands, i.e. command byte arrives as two quad nibbles.

#### `0x9F`: read ID

Observed in `test_qspi_pmod.py`:

```text
CS1 or CS2 low
send 0x9F
send 0x00 0x00 0x00
read 8 bytes
CS high
```

Effect:

```text
no mode change
```

A behavioural simulation model can return fixed nonzero ID bytes. The exact ID value is less important for TinyQV scripts unless they assert a specific value.

#### `0x02`: SPI write

Observed in `test_psram.py` before QPI setup.

```text
CS1 or CS2 low
send 0x02
send 24-bit address, MSB first
send data bytes on SD0
CS high
```

Effect:

```text
ram[address + i] = data[i]
```

#### `0x03`: SPI read

Observed in `test_psram.py` before QPI setup.

```text
CS1 or CS2 low
send 0x03
send 24-bit address, MSB first
read data bytes on SD1
CS high
```

Effect:

```text
no mode change
```

### 4.4 PSRAM QPI mode formats

These are the formats relevant to your externalized-state RISC-V core after RP2040 setup.

#### `0x0B`: QPI fast read

```text
CS1 or CS2 low
send command 0x0B over SD[3:0]: 2 quad cycles
send 24-bit address over SD[3:0]: 6 quad cycles
turn bus around to input after dummy phase as implemented by controller
clock dummy cycles, TinyQV-style model uses 4 quad cycles
read data: 2 quad cycles per byte
CS high
```

Recommended simulation model behaviour:

```text
if ram_qpi_mode and command == 0x0B:
    after address + dummy, stream ram[address], ram[address+1], ...
```

#### `0x02`: QPI write

```text
CS1 or CS2 low
send command 0x02 over SD[3:0]: 2 quad cycles
send 24-bit address over SD[3:0]: 6 quad cycles
send write data: 2 quad cycles per byte
CS high
```

Recommended simulation model behaviour:

```text
if ram_qpi_mode and command == 0x02:
    ram[address + i] = data[i]
```

#### `0xF5`: exit QPI mode

Not used by TinyQV runtime scripts, but useful for a complete model.

```text
CS1 or CS2 low
send command 0xF5 over SD[3:0]: 2 quad cycles
CS high
```

Effect:

```text
selected_ram_qpi_mode = 0
```

---

## 5. TinyQV RP2040 Init Flow: From Power-On to Runtime Mode

This is the subset that matters if you want the PMOD to reach the same state expected by TinyQV before the FPGA/core starts driving it.

### 5.1 Initial board-control assumptions

The RP2040 script performs these board-level actions:

```text
set RP2040 frequency
set many pins to input/no-pull
hold FPGA reset/config line low through ice_creset_b
configure flash
configure RAM A and RAM B
release FPGA reset/config line
wait for FPGA done
pulse project reset/clock
release QSPI pins to inputs/pulls
start project clock
```

For PMOD memory modelling, only the flash/RAM command sequences matter. The reset/clock handoff matters for a board-level testbench, not for a pure memory device model.

### 5.2 Flash setup sequence used by `setup_flash()`

Goal:

```text
Put flash into continuous quad-I/O read mode.
```

Sequence:

```text
1. Use SPI controller at 32 MHz.
2. Select flash CS0.
3. Send 0xFF.
4. Deselect flash.
5. Use RP2040 PIO QSPI helper at 16 MHz.
6. Perform one 0xEB quad-I/O read from address 0x000000 with mode byte 0xAA.
7. Clock 4 dummy quad cycles.
8. Read 1 byte, i.e. 2 quad data cycles.
9. Deselect flash.
```

Detailed bus sequence for step 6:

```text
CS0 low
command 0xEB on SD0, MSB first: 8 SPI bit-cycles
address 0x000000 over SD[3:0]: 6 quad cycles
mode 0xAA over SD[3:0]: 2 quad cycles
bus direction changes to input
4 dummy quad cycles
read 2 quad nibbles = 1 byte
CS0 high
```

Mode result:

```text
flash_continuous_mode = 1
```

### 5.3 RAM setup sequence used by `setup_ram()`

Goal:

```text
Put both PSRAM chips into QPI mode.
```

Sequence for each RAM chip:

```text
CS high for all memories initially
select RAM A, send 0x35, deselect RAM A
select RAM B, send 0x35, deselect RAM B
```

Detailed bus sequence:

```text
CS1 low
send 0x35 serially on SD0, MSB first
CS1 high

CS2 low
send 0x35 serially on SD0, MSB first
CS2 high
```

Mode result:

```text
ram_a_qpi_mode = 1
ram_b_qpi_mode = 1
```

### 5.4 Runtime state after `setup_flash()` and `setup_ram()`

After the init sequence, the core is expected to use the PMOD like this:

| Device | Select | Runtime protocol |
|---|---|---|
| Flash | `CS0` low | Continuous read: address → mode → dummy → data |
| RAM A | `CS1` low | QPI command protocol |
| RAM B | `CS2` low | QPI command protocol |

The core should not need to send:

```text
flash 0xEB setup
PSRAM 0x35 setup
flash programming commands
```

unless the design intentionally takes over board initialization.

---

## 6. TinyQV Runtime Access Subset

This is the small subset your RISC-V core / `qspi_ctrl.v` likely needs.

### 6.1 Instruction flash read, continuous mode

```text
Precondition:
    flash_continuous_mode = 1

Transaction:
    CS0 low
    send 24-bit byte address over SD[3:0], high nibble first
    send mode byte over SD[3:0]
        use 0xAA to remain in continuous mode
        use 0xFF to exit continuous mode
    release SD[3:0] / switch to input
    clock 4 dummy quad cycles
    sample data, 2 quad cycles per byte
    CS0 high
```

For a 32-bit instruction fetch:

```text
6 address cycles
2 mode cycles
4 dummy cycles
8 data cycles for 4 bytes
```

Total after CS assertion:

```text
20 SCK cycles, excluding any controller-specific CS setup/hold cycles
```

If instructions are stored little-endian in flash memory:

```text
flash[pc + 0] = instr[7:0]
flash[pc + 1] = instr[15:8]
flash[pc + 2] = instr[23:16]
flash[pc + 3] = instr[31:24]
```

### 6.2 PSRAM QPI read

```text
Precondition:
    selected RAM has qpi_mode = 1

Transaction:
    CS1 or CS2 low
    send command 0x0B over SD[3:0]: 2 cycles
    send 24-bit byte address over SD[3:0]: 6 cycles
    release SD[3:0] / switch to input
    clock dummy cycles; TinyQV-style model uses 4 cycles
    sample data, 2 cycles per byte
    CS high
```

For a 32-bit register/memory read:

```text
2 command cycles
6 address cycles
4 dummy cycles
8 data cycles for 4 bytes
```

Total after CS assertion:

```text
20 SCK cycles, excluding controller-specific CS setup/hold cycles
```

### 6.3 PSRAM QPI write

```text
Precondition:
    selected RAM has qpi_mode = 1

Transaction:
    CS1 or CS2 low
    send command 0x02 over SD[3:0]: 2 cycles
    send 24-bit byte address over SD[3:0]: 6 cycles
    send data, 2 cycles per byte
    CS high
```

For a 32-bit write:

```text
2 command cycles
6 address cycles
8 data cycles for 4 bytes
```

Total after CS assertion:

```text
16 SCK cycles, excluding controller-specific CS setup/hold cycles
```

### 6.4 Nibble ordering

For all QPI/QSPI multi-nibble fields in the TinyQV-style model:

```text
high nibble first, then low nibble
```

Examples:

```text
0x0B command in QPI: 0x0, then 0xB
0x02 command in QPI: 0x0, then 0x2
24-bit address 0x123456: 0x1, 0x2, 0x3, 0x4, 0x5, 0x6
byte 0xAB data: 0xA, then 0xB
```

---

## 7. Programming / Test Utility Subset

These commands are not needed for the TinyQV core runtime, but they appear in the MicroPython helper scripts and are useful if the Verilog PMOD model is meant to emulate the full board environment.

### 7.1 Flash programming flow

Goal:

```text
Erase/program/verify flash contents from an RP2040 script.
```

Observed flow:

```text
optional: send 0xAB, wait conservatively
send 0x90 ID command and print response
for each 4096-byte sector:
    send 0x06 write enable
    send 0x20 sector erase with sector address
    poll 0x05 until busy bit clears
    for each 256-byte page chunk:
        send 0x06 write enable
        send 0x02 page program with address and data
        poll 0x05 until busy bit clears
verify:
    send 0x03 normal read at each programmed address
    compare returned data
```

### 7.2 PSRAM SPI-mode test flow

Goal:

```text
Test PSRAM read/write before QPI setup.
```

Observed flow:

```text
for RAM A and RAM B:
    repeat random tests:
        choose random address
        write 8 random bytes using SPI 0x02
        read 8 bytes using SPI 0x03
        compare bytes
```

This means a complete PMOD simulation model should not only model QPI PSRAM runtime; it should also understand SPI-mode `0x02` and `0x03` before the `0x35` QPI-entry command.

### 7.3 PMOD ID sanity test flow

Observed test flow:

```text
Flash:
    0x90 + address/dummy, read ID bytes
    0x9F, read JEDEC ID bytes

RAM A:
    0x9F + 0x000000, read 8 ID bytes

RAM B:
    0x9F + 0x000000, read 8 ID bytes
```

The ID values are primarily used for observation/printing in the provided scripts, not as strict pass/fail checks.

---

## 8. Bus Timing / Cycle Gaps Observed in Scripts

### 8.1 Within SPI/QSPI memory transactions

The MicroPython helper functions do not insert explicit software delays between CS assertion and the first byte/clock of a command. The transaction pattern is:

```text
CS low
write command/address/data and/or read data
CS high
```

For a behavioural Verilog model, it is reasonable to accept commands immediately after CS goes low, as long as the first sampled SCK edge occurs with CS low.

### 8.2 Flash continuous-read PIO timing

The QSPI PIO helper is instantiated at:

```text
16 MHz state machine rate
```

It emits one output item per QSPI/SPI cycle while toggling `SCK` using side-set. The meaningful cycle counts are therefore the counts listed earlier:

```text
0xEB setup read:
    8 command bit-cycles
    6 address quad cycles
    2 mode quad cycles
    4 dummy quad cycles
    2 cycles per data byte

continuous read:
    6 address quad cycles
    2 mode quad cycles
    4 dummy quad cycles
    2 cycles per data byte
```

### 8.3 Flash programming waits

The programming scripts wait for flash write/erase completion by polling SR1 bit 0:

```text
poll 0x05
if bit0 == 1, sleep 10 ms and poll again
```

For a simulation model, you can either:

```text
make erase/program complete immediately and return SR1 bit0 = 0
```

or:

```text
set busy for a small fixed number of simulation cycles/transactions
```

Immediate completion is enough for most functional tests.

### 8.4 Wake wait after `0xAB`

One helper sends `0xAB` then waits:

```text
1 second
```

This is a conservative script delay. A hardware model does not need to enforce a one-second delay unless the goal is to reproduce the exact script timing.

### 8.5 Board handoff delays in `run_tinyqv.py`

The board-control script includes non-memory delays:

```text
hold FPGA reset/config low during PMOD setup
sleep 10 us before releasing FPGA config/reset
wait for FPGA done
project reset/clock pulse delays of about 1 ms
10 slow clock pulses with about 1 ms low and 1 ms high
release PMOD pins to inputs/pulls
wait about 1 ms
start project clock at 14 MHz
```

These are board/handoff behaviours, not memory-chip command timings.

---

## 9. Recommended Verilog Behavioural Model State Variables

A complete simulation model should track at least:

```verilog
reg flash_continuous_mode;
reg flash_write_enable;
reg flash_busy;

reg ram_a_qpi_mode;
reg ram_b_qpi_mode;
```

Optional but useful:

```verilog
reg flash_powered_down;
reg flash_reset_armed;
reg ram_a_reset_armed;
reg ram_b_reset_armed;
```

### 9.1 Minimum model for core runtime only

If the model is only for testing `core.v` / `qspi_ctrl.v` after RP2040 init:

```text
Required:
    flash continuous read: address/mode/dummy/data
    PSRAM QPI 0x0B read
    PSRAM QPI 0x02 write

Initial state:
    flash_continuous_mode = 1
    ram_a_qpi_mode = 1
    ram_b_qpi_mode = 1
```

### 9.2 Complete TinyQV MicroPython-compatible model

If the model should support all behaviours observed in the MicroPython folder:

```text
Flash:
    0xFF leave continuous mode
    0xAB wake
    0x90 ID
    0x9F JEDEC ID
    0x06 write enable
    0x05 read SR1 busy bit
    0x20 sector erase
    0x02 page program
    0x03 normal read
    0xEB quad-I/O read with mode-byte CM entry/exit
    commandless continuous read

PSRAM:
    SPI 0x9F ID
    SPI 0x02 write
    SPI 0x03 read
    SPI 0x35 enter QPI
    QPI 0x0B read
    QPI 0x02 write
    optional QPI 0xF5 exit QPI
```

---

## 10. Practical Notes for Your RISC-V Externalized-State Core

### 10.1 Suggested memory map at PMOD level

You can use device select rather than a shared address map:

```text
CS0 / flash: instruction memory / boot ROM
CS1 / RAM A: register file image or data memory
CS2 / RAM B: data memory or second memory bank
```

### 10.2 Suggested file format for simulation memory images

Use byte-addressed hex files:

```text
one byte per line
hexadecimal
little-endian storage for 32-bit RISC-V words
```

Example: RISC-V `nop = 0x00000013` stored at address 0:

```text
13
00
00
00
```

### 10.3 Expected controller direction changes

A correct `qspi_ctrl.v` should:

```text
Drive SD[3:0] during command/address/mode/write-data phases.
Release SD[3:0] during dummy/read-data phases.
Sample read data after the PMOD has had a falling edge or equivalent setup phase to drive the bus.
Keep exactly one CS line low during a transaction.
Return all CS lines high between transactions.
```

### 10.4 Common off-by-one traps

```text
24-bit address in quad mode is 6 SCK cycles, not 24.
One byte of QPI data is 2 SCK cycles, not 8.
Flash continuous-mode read has no 0xEB command byte.
Flash setup read does have the 0xEB command byte.
PSRAM command 0x02 means write in both SPI mode and QPI mode, but the bus width is different.
Flash command 0x02 is page program, not RAM-style overwrite; erased state and write-enable matter.
```

---

## 11. Source Basis

This document is consolidated from:

- TinyTapeout QSPI PMOD board documentation and store listing.
- TinyTapeout pinout documentation.
- Winbond W25Q128JV-family flash command behaviour.
- AP Memory APS6404L-3SQR PSRAM command behaviour.
- TinyQV MicroPython files inspected in this conversation:
  - `run_tinyqv.py`
  - `test_qspi_read.py`
  - `test_qspi_pmod.py`
  - `test_psram.py`
  - `flash_prog.py`
  - `fpga_flash_prog.py`
  - `prog_fpga.py`

