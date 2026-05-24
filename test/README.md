# QSPI-integrated core test scaffold

This directory is organized around two phases:

## Phase A: board/RP2040-style PMOD init

Implemented by:

- `include/qspi_host.py`
- `include/qspi_init.py`
- `top_qspi_tb.v`

`top_qspi_tb.v` exposes a temporary `host_*` QSPI master. Cocotb drives this host while the core is held in reset, initializes the PMOD, then releases the bus to the core.

## Phase B: per-test core behavior

Each test should:

1. Build `mem/flash.hex`, `mem/rama.hex`, and `mem/ramb.hex`.
2. Mirror those images into `dut.pmod.*` arrays using `load_images_into_pmod()`.
3. Call `init_qspi_pmod(dut)`.
4. Run the core and assert external memory/register state.

Example:

```bash
cd test
make -f test_qspi_add.mk
```

## Memory mapping used by current core

- Flash / instruction memory: `qspi_cs_n[0]`
- External register file: `qspi_cs_n[1]`, 32-bit register at `reg_index * 4`
- External data memory: `qspi_cs_n[2]`

## Word byte order

The current `qspi_ctrl.v` assembles received 32-bit words MS-nibble first, so the helpers use `set_word_qspi()`:

```text
0x002081B3 -> 00 20 81 B3
```

This matches the current RTL. If `qspi_ctrl.v` later changes to assemble little-endian flash words, update `mem_image.py`.
