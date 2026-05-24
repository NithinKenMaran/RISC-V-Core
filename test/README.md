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
 ** test                                 status  sim time (ns)  real time (s)  ratio (ns/s) **
 *********************************************************************************************
 ** test_core.test_add                    pass        8050.00           0.19      41707.26  **
 ** test_core.test_sub                    pass        8050.00           0.06     133519.00  **
 ** test_core.test_sll                    pass        8050.00           0.06     134820.40  **
 ** test_core.test_slt                    pass        8050.00           0.06     135064.17  **
 ** test_core.test_sltu                   pass        8050.00           0.06     134874.26  **
 ** test_core.test_xor                    pass        8050.00           0.06     134287.41  **
 ** test_core.test_srl                    pass        8050.00           0.06     134653.72  **
 ** test_core.test_sra                    pass        8050.00           0.06     134836.01  **
 ** test_core.test_or                     pass        8050.00           0.06     134561.42  **
 ** test_core.test_and                    pass        8050.00           0.06     134848.40  **
 ** test_core.test_addi                   pass        8050.00           0.06     135225.91  **
 ** test_core.test_slti                   pass        8050.00           0.06     133368.69  **
 ** test_core.test_sltiu                  pass        8050.00           0.06     134691.86  **
 ** test_core.test_xori                   pass        8050.00           0.06     132923.97  **
 ** test_core.test_ori                    pass        8050.00           0.06     134451.57  **
 ** test_core.test_andi                   pass        8050.00           0.06     134770.89  **
 ** test_core.test_slli                   pass        8050.00           0.06     135155.54  **
 ** test_core.test_srli                   pass        8050.00           0.06     134478.35  **
 ** test_core.test_srai                   pass        8050.00           0.06     134983.17  **
 ** test_core.test_lui                    pass        8050.00           0.06     135339.19  **
 ** test_core.test_auipc                  pass        8050.00           0.06     134774.66  **
 ** test_core.test_lw                     pass       16050.00           0.10     162573.07  **
 ** test_core.test_sw                     pass       24050.00           0.11     227162.82  **
 ** test_core.test_lb_negative            pass       24050.00           0.11     227169.48  **
 ** test_core.test_lb_positive            pass       24050.00           0.11     226501.77  **
 ** test_core.test_lbu_0xff               pass       24050.00           0.11     225671.24  **
 ** test_core.test_lbu_0x80               pass       24050.00           0.14     175590.13  **
 ** test_core.test_lh_negative            pass       24050.00           0.11     225940.15  **
 ** test_core.test_lh_positive            pass       24050.00           0.11     227223.21  **
 ** test_core.test_lhu_negative           pass       24050.00           0.11     228154.45  **
 ** test_core.test_sb_offset0             pass       48050.00           0.18     273639.50  **
 ** test_core.test_sb_offset1             pass       48050.00           0.18     271084.72  **
 ** test_core.test_sb_offset2             pass       48050.00           0.17     274839.98  **
 ** test_core.test_sb_offset3             pass       48050.00           0.18     273815.72  **
 ** test_core.test_sh_offset0             pass       48050.00           0.18     272509.87  **
 ** test_core.test_sh_offset2             pass       48050.00           0.18     272768.05  **
 ** test_core.test_lh_misalign            pass       32050.00           0.13     247936.49  **
 ** test_core.test_lhu_misalign           pass       32050.00           0.13     246980.79  **
 ** test_core.test_lw_misalign            pass       32050.00           0.13     247785.22  **
 ** test_core.test_sh_misalign            pass       32050.00           0.13     247683.41  **
 ** test_core.test_sw_misalign            pass       32050.00           0.13     247379.85  **
 ** test_core.test_sb_unaligned_no_trap   pass       48050.00           0.18     271863.63  **
 ** test_core.test_lb_unaligned_no_trap   pass       24050.00           0.11     226559.25  **
 ** test_core.test_fence                  pass       24050.00           0.11     226856.81  **
 ** test_core.test_beq                    pass       32050.00           0.13     247192.43  **
 ** test_core.test_bne                    pass       32050.00           0.13     247992.29  **
 ** test_core.test_blt                    pass       32050.00           0.13     246551.82  **
 ** test_core.test_bge                    pass       32050.00           0.13     248295.99  **
 ** test_core.test_bltu                   pass       32050.00           0.13     248155.27  **
 ** test_core.test_bgeu                   pass       32050.00           0.13     246965.37  **
 ** test_core.test_jal                    pass       16050.00           0.08     194514.03  **
 ** test_core.test_jalr                   pass       24050.00           0.11     225451.34  **
 ** test_core.test_ecall                  pass       32050.00           0.13     248088.41  **
 ** test_core.test_ebreak                 pass       32050.00           0.13     246312.84  **
 *********************************************************************************************
 ** tests=54 pass=54 fail=0 skip=0                 1218700.05           5.77     211130.64  **
 *********************************************************************************************
                                                         

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
