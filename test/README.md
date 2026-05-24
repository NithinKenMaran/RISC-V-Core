# QSPI-integrated core test scaffold

## Usage

```bash
cd test
make -f test_core.mk
```

Runs one instance of each supported RV32I instruction type as a preliminary smoke test — a quick confirmation that the core is functionally intact before deeper per-instruction testing.

Instruction groups covered: R-type ALU (ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND), I-type ALU (ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI), U-type (LUI, AUIPC), memory (LW, SW), branches (BEQ, BNE, BLT, BGE, BLTU, BGEU), and jumps (JAL, JALR).

## Expected output

Cocotb runs each `@cocotb.test()` in sequence and prints a summary at the end:

```
...
TESTCASE    test_add        PASS
TESTCASE    test_sub        PASS
TESTCASE    test_sll        PASS
...
TESTCASE    test_jalr       PASS

** TEST                          STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
** test_core.test_add             PASS        8000.00           ...          ...     **
...
** TESTS=32 PASS=32 FAIL=0 SKIP=0 **
```

A failing assertion prints which instruction failed and the actual vs. expected register value, e.g.:

```
AssertionError: ADD: expected 30, got 0
```

## How the simulation is structured

### Phase A: QSPI PMOD initialisation

Before the core is released from reset, `top_qspi_tb.v` exposes a temporary `host_*` QSPI master. Cocotb drives this host to configure the QSPI PMOD (setting quad-mode flags, etc.), then hands the bus over to the core.

Implemented by:
- `include/qspi_host.py`
- `include/qspi_init.py`
- `top_qspi_tb.v`

### Phase B: per-test core behaviour

Each test builds flash and RAM images, loads them into the emulated PMOD, resets the core, runs it for N clock cycles, then asserts register or memory state.

1. Build `mem/flash.hex`, `mem/rama.hex`, and `mem/ramb.hex`.
2. Mirror those images into `dut.pmod.*` arrays using `load_images_into_pmod()`.
3. Call `init_qspi_pmod(dut)`.
4. Run the core and assert external memory/register state.

### The QSPI PMOD board is emulated in simulation

`qspi_pmod.v` is a behavioural model of the physical QSPI PMOD board. It responds to the same SPI transactions the real board would, backed by plain Verilog arrays (`flash[]`, `ram_a[]`, `ram_b[]`). This means:

- The core exercises its actual `qspi_ctrl.v` state machine — no shortcuts.
- Test assertions read directly from `dut.pmod.ram_a` / `dut.pmod.ram_b`, the same arrays the emulated board writes to.
- No real SPI hardware or RP2040 is needed to run the tests.

## Memory mapping

| Region              | Chip-select      | Notes                         |
|---------------------|------------------|-------------------------------|
| Flash / instruction | `qspi_cs_n[0]`   |                               |
| External reg file   | `qspi_cs_n[1]`   | 32-bit register at `reg * 4`  |
| External data mem   | `qspi_cs_n[2]`   |                               |

## Word byte order

`qspi_ctrl.v` assembles received 32-bit words MS-nibble first, so helpers use `set_word_qspi()`:

```text
0x002081B3 -> 00 20 81 B3
```

If `qspi_ctrl.v` later changes to little-endian flash words, update `mem_image.py`.
