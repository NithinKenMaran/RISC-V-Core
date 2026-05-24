# test/test_core.py
#
# One-of-each smoke test for every supported RV32I instruction.
#
# NOT IMPLEMENTED (remaining RV32I work):
#   CSR            : CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI
#   Trap features  : mtvec, mepc, mcause, mtval as CSRs; mret; interrupts;
#                    nested traps; non-terminal trap return

import sys
from pathlib import Path

import cocotb

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR / "include"))

from mem_image import MemoryImage, reg_addr, load_images_into_pmod, read_word_from_pmod_array
from qspi_host import start_system_clock, wait_core_cycles
from qspi_init import init_qspi_pmod
from riscv_encode import (
    encode_nop,
    encode_add, encode_sub, encode_sll, encode_slt, encode_sltu,
    encode_xor, encode_srl, encode_sra, encode_or, encode_and,
    encode_addi, encode_slti, encode_sltiu, encode_xori, encode_ori, encode_andi,
    encode_slli, encode_srli, encode_srai,
    encode_lui, encode_auipc,
    encode_lb, encode_lh, encode_lw, encode_lbu, encode_lhu,
    encode_sb, encode_sh, encode_sw,
    encode_beq, encode_bne, encode_blt, encode_bge, encode_bltu, encode_bgeu,
    encode_jal, encode_jalr,
    encode_ecall, encode_ebreak,
    encode_fence,
)

# ── Shared test runner ────────────────────────────────────────────────────────

async def run_test(dut, flash_img, rama_img, ramb_img, cycles=800):
    """Load images, reset core, run for `cycles` core clock cycles."""
    mem_dir = TEST_DIR / "mem"
    flash_img.write_hex(mem_dir / "flash.hex")
    rama_img.write_hex(mem_dir / "rama.hex")
    ramb_img.write_hex(mem_dir / "ramb.hex")
    # Clear stale PMOD state from previous tests. load_images_into_pmod only
    # writes touched bytes, so leftovers from longer tests can corrupt shorter
    # ones (e.g. a branch test's tail instruction running in a JAL test).
    # 128 bytes covers all instructions + all 32 registers any test uses.
    for i in range(128):
        dut.pmod.flash[i].value = 0
    for i in range(128):
        dut.pmod.ram_a[i].value = 0
    await load_images_into_pmod(dut, flash_img, rama_img, ramb_img)
    # Start a fresh clock each test. cocotb cancels background tasks between
    # tests, so the previous Clock coroutine is already gone by the time the
    # next test begins.
    await start_system_clock(dut, period_ns=10)
    # strict=False: set mode flags directly instead of replaying SPI init
    # transactions; faster and safe once devices are in the right mode.
    await init_qspi_pmod(dut, strict=False)
    await wait_core_cycles(dut, cycles)


# ── Image builders ────────────────────────────────────────────────────────────

def rtype_images(instr_word, a, b):
    """Single R-type instruction: rd=x3, rs1=x1=a, rs2=x2=b."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, instr_word)
    flash.set_word_qspi(0x0004, encode_nop())
    flash.set_word_qspi(0x0008, encode_nop())
    rama.set_word_qspi(reg_addr(1), a)
    rama.set_word_qspi(reg_addr(2), b)
    return flash, rama, ramb


def itype_images(instr_word, a):
    """Single I-type ALU instruction: rd=x3, rs1=x1=a."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, instr_word)
    flash.set_word_qspi(0x0004, encode_nop())
    flash.set_word_qspi(0x0008, encode_nop())
    rama.set_word_qspi(reg_addr(1), a)
    return flash, rama, ramb


def utype_images(instr_word):
    """Single U-type instruction (LUI/AUIPC): rd=x3, no source registers."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, instr_word)
    flash.set_word_qspi(0x0004, encode_nop())
    flash.set_word_qspi(0x0008, encode_nop())
    return flash, rama, ramb


def branch_images(x1_val, x2_val, branch_instr):
    """
    Program layout:
      0x00: addi x1, x0, x1_val      <- setup
      0x04: addi x2, x0, x2_val      <- setup
      0x08: branch x1, x2, +8        <- if taken -> 0x10
      0x0C: addi x5, x0, 0xFF        <- skipped when branch taken
      0x10: addi x5, x0, 0x42        <- sentinel: verify x5==0x42
      0x14: nop
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_addi(1, 0, x1_val))
    flash.set_word_qspi(0x0004, encode_addi(2, 0, x2_val))
    flash.set_word_qspi(0x0008, branch_instr)
    flash.set_word_qspi(0x000C, encode_addi(5, 0, 0xFF))
    flash.set_word_qspi(0x0010, encode_addi(5, 0, 0x42))
    flash.set_word_qspi(0x0014, encode_nop())
    return flash, rama, ramb


def read_reg(dut, reg_index):
    return read_word_from_pmod_array(dut.pmod.ram_a, reg_addr(reg_index))


# ── Trap image builder (for ECALL/EBREAK/misalignment traps) ─────────────────
#
# Flash layout:
#   0x0000 : trap-triggering instruction (or setup + trap)
#   ...
#   0xF000 : addi x5, x0, 0x42   <- trap handler sentinel
#   0xF004 : jal x0, 0            <- loop forever
#
# Internal trap registers accessed via dut.dut.trap_valid / trap_epc /
# trap_cause / trap_tval (dut = top_qspi_tb; dut.dut = core instance).

TRAP_VECTOR    = 0x0000_F000
TRAP_SENTINEL  = 0x42


def trap_images(trap_instr):
    """Flash image for a terminal trap test (ECALL / EBREAK)."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, trap_instr)
    flash.set_word_qspi(0x0004, encode_addi(3, 0, 0xFF))    # must be skipped
    flash.set_word_qspi(TRAP_VECTOR + 0, encode_addi(5, 0, TRAP_SENTINEL))
    flash.set_word_qspi(TRAP_VECTOR + 4, encode_jal(0, 0))  # jal x0, 0
    return flash, rama, ramb


def misalign_trap_images(setup_instrs, trap_instr):
    """
    Flash image for an alignment-trap test.
    setup_instrs: list of (addr_offset, encoded_word) tuples placed before trap_instr.
    trap_instr is placed at the address immediately after all setup instructions.

    Trap handler at TRAP_VECTOR writes sentinel x5=0x42 and loops.
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    next_addr = 0x0000
    for word in setup_instrs:
        flash.set_word_qspi(next_addr, word)
        next_addr += 4
    flash.set_word_qspi(next_addr, trap_instr)
    next_addr += 4
    flash.set_word_qspi(next_addr, encode_addi(3, 0, 0xFF))  # must NOT execute
    flash.set_word_qspi(TRAP_VECTOR + 0, encode_addi(5, 0, TRAP_SENTINEL))
    flash.set_word_qspi(TRAP_VECTOR + 4, encode_jal(0, 0))
    return flash, rama, ramb, next_addr - 4  # return PC of trapping instruction


# ── R-type ALU ────────────────────────────────────────────────────────────────

@cocotb.test()
async def test_add(dut):
    f, ra, rb = rtype_images(encode_add(3, 1, 2), 10, 20)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 30, f"ADD: expected 30, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_sub(dut):
    f, ra, rb = rtype_images(encode_sub(3, 1, 2), 20, 10)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 10, f"SUB: expected 10, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_sll(dut):
    f, ra, rb = rtype_images(encode_sll(3, 1, 2), 1, 4)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 16, f"SLL: expected 16, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_slt(dut):
    # -1 (0xFFFFFFFF) < 1 signed -> 1
    f, ra, rb = rtype_images(encode_slt(3, 1, 2), 0xFFFFFFFF, 1)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 1, f"SLT: expected 1, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_sltu(dut):
    # 5 < 10 unsigned -> 1
    f, ra, rb = rtype_images(encode_sltu(3, 1, 2), 5, 10)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 1, f"SLTU: expected 1, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_xor(dut):
    f, ra, rb = rtype_images(encode_xor(3, 1, 2), 0b1100, 0b1010)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b0110, f"XOR: expected 6, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_srl(dut):
    # logical shift: sign bit not propagated
    f, ra, rb = rtype_images(encode_srl(3, 1, 2), 0x80000000, 4)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0x08000000, f"SRL: expected 0x08000000, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_sra(dut):
    # arithmetic shift: sign bit propagated
    f, ra, rb = rtype_images(encode_sra(3, 1, 2), 0x80000000, 4)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0xF8000000, f"SRA: expected 0xF8000000, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_or(dut):
    f, ra, rb = rtype_images(encode_or(3, 1, 2), 0b1100, 0b1010)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b1110, f"OR: expected 14, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_and(dut):
    f, ra, rb = rtype_images(encode_and(3, 1, 2), 0b1100, 0b1010)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b1000, f"AND: expected 8, got {read_reg(dut, 3)}"


# ── I-type ALU ────────────────────────────────────────────────────────────────

@cocotb.test()
async def test_addi(dut):
    f, ra, rb = itype_images(encode_addi(3, 1, 7), 10)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 17, f"ADDI: expected 17, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_slti(dut):
    # -1 (0xFFFFFFFF) < 1 signed -> 1
    f, ra, rb = itype_images(encode_slti(3, 1, 1), 0xFFFFFFFF)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 1, f"SLTI: expected 1, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_sltiu(dut):
    # 5 < 10 unsigned -> 1
    f, ra, rb = itype_images(encode_sltiu(3, 1, 10), 5)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 1, f"SLTIU: expected 1, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_xori(dut):
    f, ra, rb = itype_images(encode_xori(3, 1, 0b1010), 0b1100)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b0110, f"XORI: expected 6, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_ori(dut):
    f, ra, rb = itype_images(encode_ori(3, 1, 0b1010), 0b1100)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b1110, f"ORI: expected 14, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_andi(dut):
    f, ra, rb = itype_images(encode_andi(3, 1, 0b1010), 0b1100)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0b1000, f"ANDI: expected 8, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_slli(dut):
    f, ra, rb = itype_images(encode_slli(3, 1, 4), 1)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 16, f"SLLI: expected 16, got {read_reg(dut, 3)}"

@cocotb.test()
async def test_srli(dut):
    f, ra, rb = itype_images(encode_srli(3, 1, 4), 0x80000000)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0x08000000, f"SRLI: expected 0x08000000, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_srai(dut):
    f, ra, rb = itype_images(encode_srai(3, 1, 4), 0x80000000)
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0xF8000000, f"SRAI: expected 0xF8000000, got 0x{read_reg(dut, 3):08x}"


# ── U-type ────────────────────────────────────────────────────────────────────

@cocotb.test()
async def test_lui(dut):
    f, ra, rb = utype_images(encode_lui(3, 0x12345))
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0x12345000, f"LUI: expected 0x12345000, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_auipc(dut):
    # PC=0 when this instruction executes -> result = 0 + 0x12345000
    f, ra, rb = utype_images(encode_auipc(3, 0x12345))
    await run_test(dut, f, ra, rb)
    assert read_reg(dut, 3) == 0x12345000, f"AUIPC: expected 0x12345000, got 0x{read_reg(dut, 3):08x}"


# ── Memory: LW / SW ───────────────────────────────────────────────────────────

@cocotb.test()
async def test_lw(dut):
    """
    addi x1, x0, 4    -> x1 = 4  (byte address in data memory)
    lw   x3, 0(x1)    -> x3 = ramb[4]
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))
    flash.set_word_qspi(0x0004, encode_lw(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    ramb.set_word_qspi(4, 0x12345678)
    await run_test(dut, flash, rama, ramb, cycles=1600)
    assert read_reg(dut, 3) == 0x12345678, f"LW: expected 0x12345678, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_sw(dut):
    """
    addi x1, x0, 0x55  -> x1 = 0x55 (value to store)
    addi x2, x0, 4     -> x2 = 4    (byte address in data memory)
    sw   x1, 0(x2)     -> ramb[4] = 0x55
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 0x55))
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 4))
    flash.set_word_qspi(0x0008, encode_sw(2, 1, 0))  # mem[x2+0] = x1
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_word_from_pmod_array(dut.pmod.ram_b, 4) == 0x55, \
        f"SW: expected ramb[4]=0x55, got 0x{read_word_from_pmod_array(dut.pmod.ram_b, 4):08x}"


# ── Memory: sub-word loads ────────────────────────────────────────────────────
#
# Memory word 0x807F01FF stored at data address 4.
# Little-endian interpretation within the 32-bit word:
#   bits[ 7: 0] = 0xFF  (byte offset 0, effective_addr = 4)
#   bits[15: 8] = 0x01  (byte offset 1, effective_addr = 5)
#   bits[23:16] = 0x7F  (byte offset 2, effective_addr = 6)
#   bits[31:24] = 0x80  (byte offset 3, effective_addr = 7)

@cocotb.test()
async def test_lb_negative(dut):
    """LB from byte offset 3 (byte=0x80): sign-extended -> 0xFFFFFF80."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x807F01FF)
    # effective_addr = 4 + 3 = 7, bits[31:24] = 0x80
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 7))
    flash.set_word_qspi(0x0004, encode_lb(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0xFFFFFF80, \
        f"LB-neg: expected 0xFFFFFF80, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lb_positive(dut):
    """LB from byte offset 0 (byte=0xFF): sign-extended -> 0xFFFFFFFF."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x807F01FF)
    # effective_addr = 4, bits[7:0] = 0xFF
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))
    flash.set_word_qspi(0x0004, encode_lb(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0xFFFFFFFF, \
        f"LB-pos: expected 0xFFFFFFFF, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lbu_0xff(dut):
    """LBU from byte offset 0 (byte=0xFF): zero-extended -> 0x000000FF."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x807F01FF)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))
    flash.set_word_qspi(0x0004, encode_lbu(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0x000000FF, \
        f"LBU-0xFF: expected 0x000000FF, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lbu_0x80(dut):
    """LBU from byte offset 3 (byte=0x80): zero-extended -> 0x00000080."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x807F01FF)
    # effective_addr = 4 + 3 = 7, bits[31:24] = 0x80
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 7))
    flash.set_word_qspi(0x0004, encode_lbu(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0x00000080, \
        f"LBU-0x80: expected 0x00000080, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lh_negative(dut):
    """
    Word 0x7FFF8001 at data address 4.
    bits[15:0]  = 0x8001  (halfword at effective_addr = 4, offset bit[1]=0)
    bits[31:16] = 0x7FFF  (halfword at effective_addr = 6, offset bit[1]=1)
    LH at addr 4: 0x8001 sign-extended -> 0xFFFF8001.
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x7FFF8001)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))
    flash.set_word_qspi(0x0004, encode_lh(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0xFFFF8001, \
        f"LH-neg: expected 0xFFFF8001, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lh_positive(dut):
    """LH at addr 6 (bit[1]=1): bits[31:16]=0x7FFF sign-extended -> 0x00007FFF."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x7FFF8001)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 6))
    flash.set_word_qspi(0x0004, encode_lh(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0x00007FFF, \
        f"LH-pos: expected 0x00007FFF, got 0x{read_reg(dut, 3):08x}"

@cocotb.test()
async def test_lhu_negative(dut):
    """LHU at addr 4: 0x8001 zero-extended -> 0x00008001."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x7FFF8001)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))
    flash.set_word_qspi(0x0004, encode_lhu(3, 1, 0))
    flash.set_word_qspi(0x0008, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 3) == 0x00008001, \
        f"LHU: expected 0x00008001, got 0x{read_reg(dut, 3):08x}"


# ── Memory: sub-word stores ───────────────────────────────────────────────────
#
# SB: read-modify-write. Little-endian byte placement within the 32-bit word.
#   offset 0 -> bits[ 7: 0]; offset 1 -> bits[15: 8]
#   offset 2 -> bits[23:16]; offset 3 -> bits[31:24]

@cocotb.test()
async def test_sb_offset0(dut):
    """SB byte 0xAA at offset 0 of old word 0x11223344 -> 0x112233AA."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))    # x1 = base addr
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0xAA)) # x2 = byte to store
    flash.set_word_qspi(0x0008, encode_sb(1, 2, 0))      # mem[x1+0] byte = x2
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x112233AA, f"SB-off0: expected 0x112233AA, got 0x{got:08x}"

@cocotb.test()
async def test_sb_offset1(dut):
    """SB byte 0xAA at offset 1 of old word 0x11223344 -> 0x1122AA44."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 5))    # x1 = base+1
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0xAA))
    flash.set_word_qspi(0x0008, encode_sb(1, 2, 0))
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x1122AA44, f"SB-off1: expected 0x1122AA44, got 0x{got:08x}"

@cocotb.test()
async def test_sb_offset2(dut):
    """SB byte 0xAA at offset 2 of old word 0x11223344 -> 0x11AA3344."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 6))    # x1 = base+2
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0xAA))
    flash.set_word_qspi(0x0008, encode_sb(1, 2, 0))
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x11AA3344, f"SB-off2: expected 0x11AA3344, got 0x{got:08x}"

@cocotb.test()
async def test_sb_offset3(dut):
    """SB byte 0xAA at offset 3 of old word 0x11223344 -> 0xAA223344."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 7))    # x1 = base+3
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0xAA))
    flash.set_word_qspi(0x0008, encode_sb(1, 2, 0))
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0xAA223344, f"SB-off3: expected 0xAA223344, got 0x{got:08x}"

@cocotb.test()
async def test_sh_offset0(dut):
    """SH halfword 0x7AB at offset 0 of old word 0x11223344 -> 0x112207AB."""
    # 0x7AB = 1963, fits in signed 12-bit positive immediate.
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 4))     # x1 = base (bit[1]=0)
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0x7AB)) # x2 = 0x07AB
    flash.set_word_qspi(0x0008, encode_sh(1, 2, 0))       # mem[x1+0] hw = x2
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x112207AB, f"SH-off0: expected 0x112207AB, got 0x{got:08x}"

@cocotb.test()
async def test_sh_offset2(dut):
    """SH halfword 0x7AB at offset 2 of old word 0x11223344 -> 0x07AB3344."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 6))     # x1 = base+2 (bit[1]=1)
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0x7AB)) # x2 = 0x07AB
    flash.set_word_qspi(0x0008, encode_sh(1, 2, 0))
    flash.set_word_qspi(0x000C, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=4800)
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x07AB3344, f"SH-off2: expected 0x07AB3344, got 0x{got:08x}"


# ── Alignment traps ───────────────────────────────────────────────────────────
#
# Trap handler at TRAP_VECTOR writes x5=0x42 and loops.
# We verify: x5==0x42, trap_valid==1, trap_cause==4 or 6,
#            trap_tval==misaligned effective address, trap_epc==PC of trap instr.

@cocotb.test()
async def test_lh_misalign(dut):
    """LH at odd address (effective_addr[0]=1) traps with cause 4."""
    # addi x1, x0, 5  (address 5 = odd -> misaligned halfword)
    # lh x3, 0(x1)    <- traps at this PC = 0x0004
    flash, rama, ramb, trap_pc = misalign_trap_images(
        [encode_addi(1, 0, 5)],
        encode_lh(3, 1, 0),
    )
    await run_test(dut, flash, rama, ramb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"LH-misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    assert dut.dut.trap_valid.value == 1, "LH-misalign: trap_valid should be 1"
    assert int(dut.dut.trap_cause.value) == 4, \
        f"LH-misalign: trap_cause should be 4, got {int(dut.dut.trap_cause.value)}"
    assert int(dut.dut.trap_tval.value) == 5, \
        f"LH-misalign: trap_tval should be 5 (effective addr), got {int(dut.dut.trap_tval.value):#x}"
    assert int(dut.dut.trap_epc.value) == trap_pc, \
        f"LH-misalign: trap_epc should be {trap_pc:#x}, got {int(dut.dut.trap_epc.value):#x}"

@cocotb.test()
async def test_lhu_misalign(dut):
    """LHU at odd address traps with cause 4."""
    flash, rama, ramb, trap_pc = misalign_trap_images(
        [encode_addi(1, 0, 5)],
        encode_lhu(3, 1, 0),
    )
    await run_test(dut, flash, rama, ramb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, "LHU-misalign: trap handler not reached"
    assert dut.dut.trap_valid.value == 1
    assert int(dut.dut.trap_cause.value) == 4, \
        f"LHU-misalign: cause should be 4, got {int(dut.dut.trap_cause.value)}"
    assert int(dut.dut.trap_tval.value) == 5

@cocotb.test()
async def test_lw_misalign(dut):
    """LW at address 6 (effective_addr[1:0]!=0) traps with cause 4."""
    flash, rama, ramb, trap_pc = misalign_trap_images(
        [encode_addi(1, 0, 6)],
        encode_lw(3, 1, 0),
    )
    await run_test(dut, flash, rama, ramb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, "LW-misalign: trap handler not reached"
    assert dut.dut.trap_valid.value == 1
    assert int(dut.dut.trap_cause.value) == 4, \
        f"LW-misalign: cause should be 4, got {int(dut.dut.trap_cause.value)}"
    assert int(dut.dut.trap_tval.value) == 6

@cocotb.test()
async def test_sh_misalign(dut):
    """SH at odd address traps with cause 6."""
    # x2 = 0 by default (RAM cleared); trap fires before any write so value irrelevant.
    flash, rama, ramb, trap_pc = misalign_trap_images(
        [encode_addi(1, 0, 5)],
        encode_sh(1, 2, 0),
    )
    await run_test(dut, flash, rama, ramb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, "SH-misalign: trap handler not reached"
    assert dut.dut.trap_valid.value == 1
    assert int(dut.dut.trap_cause.value) == 6, \
        f"SH-misalign: cause should be 6, got {int(dut.dut.trap_cause.value)}"
    assert int(dut.dut.trap_tval.value) == 5

@cocotb.test()
async def test_sw_misalign(dut):
    """SW at address 6 (effective_addr[1:0]!=0) traps with cause 6."""
    flash, rama, ramb, trap_pc = misalign_trap_images(
        [encode_addi(1, 0, 6), encode_addi(2, 0, 0x55)],
        encode_sw(1, 2, 0),
    )
    await run_test(dut, flash, rama, ramb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, "SW-misalign: trap handler not reached"
    assert dut.dut.trap_valid.value == 1
    assert int(dut.dut.trap_cause.value) == 6, \
        f"SW-misalign: cause should be 6, got {int(dut.dut.trap_cause.value)}"
    assert int(dut.dut.trap_tval.value) == 6

@cocotb.test()
async def test_sb_unaligned_no_trap(dut):
    """SB at odd address does NOT trap; it stores correctly via RMW."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x11223344)
    # SB at address 5 (offset 1 within word at 4)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 5))
    flash.set_word_qspi(0x0004, encode_addi(2, 0, 0xAA))
    flash.set_word_qspi(0x0008, encode_sb(1, 2, 0))
    # jal x0, 0: halt loop so core doesn't fall into zeroed flash and trigger
    # an illegal-instruction trap that would set trap_valid.
    flash.set_word_qspi(0x000C, encode_jal(0, 0))
    await run_test(dut, flash, rama, ramb, cycles=4800)

    assert dut.dut.trap_valid.value == 0, "SB at odd addr should NOT trap"
    got = read_word_from_pmod_array(dut.pmod.ram_b, 4)
    assert got == 0x1122AA44, f"SB-unaligned: expected 0x1122AA44, got 0x{got:08x}"

@cocotb.test()
async def test_lb_unaligned_no_trap(dut):
    """LB at odd address does NOT trap."""
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    ramb.set_word_qspi(4, 0x807F01FF)
    # LB at address 5 (byte offset 1 = bits[15:8] = 0x01)
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 5))
    flash.set_word_qspi(0x0004, encode_lb(3, 1, 0))
    # halt loop: prevents core from reaching zeroed flash area
    flash.set_word_qspi(0x0008, encode_jal(0, 0))
    await run_test(dut, flash, rama, ramb, cycles=2400)

    assert dut.dut.trap_valid.value == 0, "LB at odd addr should NOT trap"
    assert read_reg(dut, 3) == 0x00000001, \
        f"LB-unaligned: expected 0x00000001, got 0x{read_reg(dut, 3):08x}"


# ── FENCE ─────────────────────────────────────────────────────────────────────

@cocotb.test()
async def test_fence(dut):
    """
    FENCE acts as NOP: execution continues normally, no trap.
      0x0000: addi x1, x0, 1
      0x0004: fence
      0x0008: addi x2, x1, 2   -> x2 = 3
      0x000C: nop
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 1))
    flash.set_word_qspi(0x0004, encode_fence())
    flash.set_word_qspi(0x0008, encode_addi(2, 1, 2))
    # halt loop: prevents core from reaching zeroed flash area
    flash.set_word_qspi(0x000C, encode_jal(0, 0))
    await run_test(dut, flash, rama, ramb, cycles=2400)

    assert read_reg(dut, 2) == 3, \
        f"FENCE: expected x2=3 after fence, got {read_reg(dut, 2)}"
    assert dut.dut.trap_valid.value == 0, "FENCE should not trap"


# ── Branches ──────────────────────────────────────────────────────────────────
# Each test verifies the branch IS taken. Sentinel register x5 must equal 0x42
# (written by the instruction at the branch target). The instruction at 0x0C
# (writes 0xFF) must have been skipped.

@cocotb.test()
async def test_beq(dut):
    # 17 == 17 -> taken
    f, ra, rb = branch_images(17, 17, encode_beq(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BEQ: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"

@cocotb.test()
async def test_bne(dut):
    # 17 != 16 -> taken
    f, ra, rb = branch_images(17, 16, encode_bne(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BNE: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"

@cocotb.test()
async def test_blt(dut):
    # 17 < 20 signed -> taken
    f, ra, rb = branch_images(17, 20, encode_blt(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BLT: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"

@cocotb.test()
async def test_bge(dut):
    # 17 >= 16 signed -> taken
    f, ra, rb = branch_images(17, 16, encode_bge(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BGE: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"

@cocotb.test()
async def test_bltu(dut):
    # 17 < 20 unsigned -> taken
    f, ra, rb = branch_images(17, 20, encode_bltu(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BLTU: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"

@cocotb.test()
async def test_bgeu(dut):
    # 17 >= 16 unsigned -> taken
    f, ra, rb = branch_images(17, 16, encode_bgeu(1, 2, 8))
    await run_test(dut, f, ra, rb, cycles=3200)
    assert read_reg(dut, 5) == 0x42, f"BGEU: expected x5=0x42, got 0x{read_reg(dut, 5):02x}"


# ── Jumps: JAL / JALR ────────────────────────────────────────────────────────

@cocotb.test()
async def test_jal(dut):
    """
    0x00: jal  x5, +8          -> x5 = 4,  PC = 8
    0x04: addi x3, x0, 0xFF    (skipped)
    0x08: addi x3, x0, 0x42    (executed)
    0x0C: nop
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_jal(5, 8))
    flash.set_word_qspi(0x0004, encode_addi(3, 0, 0xFF))
    flash.set_word_qspi(0x0008, encode_addi(3, 0, 0x42))
    # halt loop: prevents core from reaching zeroed flash, which would trigger
    # an is_illegal trap that redirects to TRAP_VECTOR and overwrites x5.
    flash.set_word_qspi(0x000C, encode_jal(0, 0))
    await run_test(dut, flash, rama, ramb, cycles=1600)
    assert read_reg(dut, 5) == 4,    f"JAL: expected x5=4 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, f"JAL: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"

@cocotb.test()
async def test_jalr(dut):
    """
    0x00: addi x1, x0, 12      -> x1 = 12
    0x04: jalr x5, x1, 0       -> x5 = 8,  PC = (12+0)&~1 = 12
    0x08: addi x3, x0, 0xFF    (skipped)
    0x0C: addi x3, x0, 0x42    (executed)
    0x10: nop
    """
    flash, rama, ramb = MemoryImage(), MemoryImage(), MemoryImage()
    flash.set_word_qspi(0x0000, encode_addi(1, 0, 12))
    flash.set_word_qspi(0x0004, encode_jalr(5, 1, 0))
    flash.set_word_qspi(0x0008, encode_addi(3, 0, 0xFF))
    flash.set_word_qspi(0x000C, encode_addi(3, 0, 0x42))
    # halt loop: same reason as test_jal — prevents stale trap handler at
    # TRAP_VECTOR from overwriting x5 and corrupting the link-register check.
    flash.set_word_qspi(0x0010, encode_jal(0, 0))
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 5) == 8,    f"JALR: expected x5=8 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, f"JALR: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"


# ── Trap: ECALL / EBREAK ──────────────────────────────────────────────────────
#
# Flash layout for trap tests:
#   0x0000 : trap instruction (ECALL or EBREAK)
#   0x0004 : addi x3, x0, 0xFF   <- must NOT execute
#   0xF000 : addi x5, x0, 0x42   <- trap handler sentinel
#   0xF004 : jal x0, 0            <- loop forever at 0xF004
#
# Internal trap registers are accessed via cocotb hierarchical path:
#   dut.dut.trap_valid / dut.dut.trap_epc / dut.dut.trap_cause / dut.dut.trap_tval
# (dut = top_qspi_tb; dut.dut = the core instance named 'dut' inside it)

@cocotb.test()
async def test_ecall(dut):
    """
    ECALL at PC=0 must redirect to TRAP_VECTOR, write sentinel to x5,
    not execute the instruction at 0x0004, and latch trap metadata.
    """
    f, ra, rb = trap_images(encode_ecall())
    await run_test(dut, f, ra, rb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"ECALL: trap handler not reached; x5={read_reg(dut, 5):#x}, expected {TRAP_SENTINEL:#x}"
    assert read_reg(dut, 3) == 0, \
        f"ECALL: instruction after trap must not execute; x3={read_reg(dut, 3):#x}"

    assert dut.dut.trap_valid.value == 1, \
        "ECALL: trap_valid should be 1"
    assert int(dut.dut.trap_epc.value) == 0, \
        f"ECALL: trap_epc should be 0, got {int(dut.dut.trap_epc.value):#x}"
    assert int(dut.dut.trap_cause.value) == 11, \
        f"ECALL: trap_cause should be 11, got {int(dut.dut.trap_cause.value)}"


@cocotb.test()
async def test_ebreak(dut):
    """
    EBREAK at PC=0 must redirect to TRAP_VECTOR, write sentinel to x5,
    not execute the instruction at 0x0004, and latch trap metadata.
    """
    f, ra, rb = trap_images(encode_ebreak())
    await run_test(dut, f, ra, rb, cycles=3200)

    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"EBREAK: trap handler not reached; x5={read_reg(dut, 5):#x}, expected {TRAP_SENTINEL:#x}"
    assert read_reg(dut, 3) == 0, \
        f"EBREAK: instruction after trap must not execute; x3={read_reg(dut, 3):#x}"

    assert dut.dut.trap_valid.value == 1, \
        "EBREAK: trap_valid should be 1"
    assert int(dut.dut.trap_epc.value) == 0, \
        f"EBREAK: trap_epc should be 0, got {int(dut.dut.trap_epc.value):#x}"
    assert int(dut.dut.trap_cause.value) == 3, \
        f"EBREAK: trap_cause should be 3, got {int(dut.dut.trap_cause.value)}"
