# test/test_core.py
#
# One-of-each smoke test for every supported RV32I instruction.
#
# NOT IMPLEMENTED (remaining RV32I work):
#   Sub-word loads : LB, LH, LBU, LHU
#   Sub-word stores: SB, SH
#   System         : FENCE, ECALL, EBREAK
#   CSR            : CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI

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
    encode_lw, encode_sw,
    encode_beq, encode_bne, encode_blt, encode_bge, encode_bltu, encode_bgeu,
    encode_jal, encode_jalr,
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
    flash.set_word_qspi(0x000C, encode_nop())
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
    flash.set_word_qspi(0x0010, encode_nop())
    await run_test(dut, flash, rama, ramb, cycles=2400)
    assert read_reg(dut, 5) == 8,    f"JALR: expected x5=8 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, f"JALR: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"
