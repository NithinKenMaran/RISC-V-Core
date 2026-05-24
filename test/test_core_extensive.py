# test/test_core_extensive.py
#
# Extensive cocotb test suite for the RV32I core.
# Self-contained: no imports from test_core.py.
#
# Covers: ALU R-type, ALU I-type, U-type, x0 invariant, register dependency
# chain, load-use coherence, branches (taken/not-taken), JAL/JALR, memory
# (word/byte/halfword loads and stores), sub-word store coherence, alignment
# traps, FENCE, ECALL, EBREAK.

import sys
from pathlib import Path

import cocotb

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR / "include"))

from mem_image import MemoryImage, reg_addr, load_images_into_pmod, read_word_from_pmod_array
from qspi_host import start_system_clock, wait_core_cycles
from qspi_init import init_qspi_pmod
from riscv_encode import (
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

# ── Constants ─────────────────────────────────────────────────────────────────

TRAP_VECTOR   = 0x0000_F000
TRAP_SENTINEL = 0x42


# ── Cycle budget ──────────────────────────────────────────────────────────────

def budget(n_instrs, n_rmw=0):
    """Conservative cycle budget. n_rmw = number of SB/SH RMW ops in program."""
    return 1600 + (n_instrs + 1) * 800 + n_rmw * 600


# ── make_prog — unified program builder ───────────────────────────────────────

def make_prog(instrs, *, regs=None, data=None, trap_handler=False):
    """
    instrs       : list of encoded 32-bit instruction words.
    regs         : dict {reg_index: value} — pre-loaded into PSRAM A (register file).
    data         : dict {byte_addr: word}  — pre-loaded into PSRAM B (data memory).
    trap_handler : if True, write addi x5,x0,TRAP_SENTINEL + jal x0,0 at TRAP_VECTOR.
    Returns (flash, rama, ramb). A mandatory 'jal x0, 0' halt loop is appended
    automatically after the last instruction.
    """
    flash = MemoryImage()
    rama  = MemoryImage()
    ramb  = MemoryImage()

    # Write instructions to flash
    addr = 0x0000
    for word in instrs:
        flash.set_word_qspi(addr, word)
        addr += 4

    # Append halt loop: jal x0, 0
    flash.set_word_qspi(addr, encode_jal(0, 0))

    # Pre-load register file into PSRAM A
    if regs:
        for reg_index, value in regs.items():
            rama.set_word_qspi(reg_addr(reg_index), int(value) & 0xFFFFFFFF)

    # Pre-load data memory into PSRAM B
    if data:
        for byte_addr, word in data.items():
            ramb.set_word_qspi(int(byte_addr), int(word) & 0xFFFFFFFF)

    # Optional trap handler at TRAP_VECTOR
    if trap_handler:
        flash.set_word_qspi(TRAP_VECTOR + 0, encode_addi(5, 0, TRAP_SENTINEL))
        flash.set_word_qspi(TRAP_VECTOR + 4, encode_jal(0, 0))

    return flash, rama, ramb


# ── run_test — load images, reset, run ────────────────────────────────────────

async def run_test(dut, flash, rama, ramb, cycles):
    """Load images, clear stale state, reset core, run for `cycles` core cycles."""
    mem_dir = TEST_DIR / "mem"
    flash.write_hex(mem_dir / "flash.hex")
    rama.write_hex(mem_dir / "rama.hex")
    ramb.write_hex(mem_dir / "ramb.hex")

    # Clear stale PMOD state from previous tests
    for i in range(128):
        dut.pmod.flash[i].value = 0
    for i in range(128):
        dut.pmod.ram_a[i].value = 0
    for i in range(128):
        dut.pmod.ram_b[i].value = 0

    await load_images_into_pmod(dut, flash, rama, ramb)
    await start_system_clock(dut, period_ns=10)
    await init_qspi_pmod(dut, strict=False)
    await wait_core_cycles(dut, cycles)


# ── Convenience wrappers ──────────────────────────────────────────────────────

def read_reg(dut, n):
    """Read register x{n} from the register file (PSRAM A)."""
    return read_word_from_pmod_array(dut.pmod.ram_a, reg_addr(n))


def read_mem(dut, addr):
    """Read a 32-bit word from data memory (PSRAM B) at byte address addr."""
    return read_word_from_pmod_array(dut.pmod.ram_b, addr)


# ── Trap assertion helper ─────────────────────────────────────────────────────

def check_trap(dut, *, valid=1, cause=None, tval=None, epc=None):
    assert dut.dut.trap_valid.value == valid, \
        f"trap_valid: expected {valid}, got {int(dut.dut.trap_valid.value)}"
    if cause is not None:
        assert int(dut.dut.trap_cause.value) == cause, \
            f"trap_cause: expected {cause}, got {int(dut.dut.trap_cause.value)}"
    if tval is not None:
        assert int(dut.dut.trap_tval.value) == tval, \
            f"trap_tval: expected {tval:#x}, got {int(dut.dut.trap_tval.value):#x}"
    if epc is not None:
        assert int(dut.dut.trap_epc.value) == epc, \
            f"trap_epc: expected {epc:#x}, got {int(dut.dut.trap_epc.value):#x}"


# ═════════════════════════════════════════════════════════════════════════════
# ALU R-type
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_add_basic(dut):
    """ADD: 10 + 20 = 30."""
    instrs = [encode_add(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 10, 2: 20})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 30, f"ADD basic: expected 30, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_add_overflow(dut):
    """ADD: 0x7FFFFFFF + 1 = 0x80000000 (signed overflow wraps)."""
    instrs = [encode_add(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x7FFFFFFF, 2: 1})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x80000000, \
        f"ADD overflow: expected 0x80000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_add_wrap(dut):
    """ADD: 0xFFFFFFFF + 1 = 0 (32-bit wrap)."""
    instrs = [encode_add(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF, 2: 1})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, \
        f"ADD wrap: expected 0, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sub_basic(dut):
    """SUB: 20 - 10 = 10."""
    instrs = [encode_sub(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 20, 2: 10})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 10, f"SUB basic: expected 10, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sub_zero(dut):
    """SUB: 5 - 5 = 0."""
    instrs = [encode_sub(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 5, 2: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"SUB zero: expected 0, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sub_borrow(dut):
    """SUB: 0 - 1 = 0xFFFFFFFF (borrow)."""
    instrs = [encode_sub(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0, 2: 1})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFFFFFF, \
        f"SUB borrow: expected 0xFFFFFFFF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sll_basic(dut):
    """SLL: 1 << 4 = 16."""
    instrs = [encode_sll(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 1, 2: 4})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 16, f"SLL basic: expected 16, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sll_by_zero(dut):
    """SLL: 0xABCD << 0 = 0xABCD."""
    instrs = [encode_sll(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0xABCD, 2: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xABCD, \
        f"SLL by zero: expected 0xABCD, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sll_by_31(dut):
    """SLL: 1 << 31 = 0x80000000."""
    instrs = [encode_sll(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 1, 2: 31})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x80000000, \
        f"SLL by 31: expected 0x80000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_slt_true(dut):
    """SLT: -1 (0xFFFFFFFF) < 1 signed → 1."""
    instrs = [encode_slt(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF, 2: 1})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLT true: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_slt_false(dut):
    """SLT: 1 < 0 signed → 0."""
    instrs = [encode_slt(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 1, 2: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"SLT false: expected 0, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_slt_min(dut):
    """SLT: 0x80000000 (-2^31) < 0 signed → 1."""
    instrs = [encode_slt(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000, 2: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLT min: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sltu_true(dut):
    """SLTU: 5 < 10 unsigned → 1."""
    instrs = [encode_sltu(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 5, 2: 10})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLTU true: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sltu_false(dut):
    """SLTU: 10 < 5 unsigned → 0."""
    instrs = [encode_sltu(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 10, 2: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"SLTU false: expected 0, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sltu_highbit(dut):
    """SLTU: 0x80000000 < 0xFFFFFFFF unsigned → 1."""
    instrs = [encode_sltu(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000, 2: 0xFFFFFFFF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLTU highbit: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_xor_basic(dut):
    """XOR: 0b1100 ^ 0b1010 = 0b0110."""
    instrs = [encode_xor(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100, 2: 0b1010})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b0110, f"XOR basic: expected 6, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_xor_ones(dut):
    """XOR: x ^ x = 0."""
    instrs = [encode_xor(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0xDEAD, 2: 0xDEAD})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"XOR ones: expected 0, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_srl_basic(dut):
    """SRL: 0x80000000 >> 4 = 0x08000000 (logical, no sign propagation)."""
    instrs = [encode_srl(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000, 2: 4})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x08000000, \
        f"SRL basic: expected 0x08000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_srl_by_31(dut):
    """SRL: 0x80000000 >> 31 = 1."""
    instrs = [encode_srl(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000, 2: 31})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SRL by 31: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sra_negative(dut):
    """SRA: 0x80000000 >> 4 = 0xF8000000 (arithmetic, sign propagates)."""
    instrs = [encode_sra(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000, 2: 4})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xF8000000, \
        f"SRA negative: expected 0xF8000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sra_positive(dut):
    """SRA: 0x00000080 >> 4 = 0x00000008 (positive, no sign propagation)."""
    instrs = [encode_sra(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0x00000080, 2: 4})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00000008, \
        f"SRA positive: expected 0x00000008, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_or_basic(dut):
    """OR: 0b1100 | 0b1010 = 0b1110."""
    instrs = [encode_or(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100, 2: 0b1010})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b1110, f"OR basic: expected 14, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_and_basic(dut):
    """AND: 0b1100 & 0b1010 = 0b1000."""
    instrs = [encode_and(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100, 2: 0b1010})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b1000, f"AND basic: expected 8, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_and_zero(dut):
    """AND: 0xFFFFFFFF & 0 = 0."""
    instrs = [encode_and(3, 1, 2)]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF, 2: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"AND zero: expected 0, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# ALU I-type
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_addi_basic(dut):
    """ADDI: x1=10, addi 7 → 17."""
    instrs = [encode_addi(3, 1, 7)]
    f, ra, rb = make_prog(instrs, regs={1: 10})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 17, f"ADDI basic: expected 17, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_addi_neg_imm(dut):
    """ADDI: x1=0, addi -1 (imm=0xFFF) → 0xFFFFFFFF."""
    instrs = [encode_addi(3, 1, 0xFFF)]
    f, ra, rb = make_prog(instrs, regs={1: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFFFFFF, \
        f"ADDI neg imm: expected 0xFFFFFFFF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_addi_max_pos_imm(dut):
    """ADDI: x1=0, addi 2047 → 2047."""
    instrs = [encode_addi(3, 1, 2047)]
    f, ra, rb = make_prog(instrs, regs={1: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 2047, \
        f"ADDI max pos imm: expected 2047, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_addi_neg_base(dut):
    """ADDI: x1=0xFFFFFFFF (-1), addi 1 → 0."""
    instrs = [encode_addi(3, 1, 1)]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, \
        f"ADDI neg base: expected 0, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_slti_true(dut):
    """SLTI: x1=0xFFFFFFFF (-1), slti 1 → 1 (since -1 < 1 signed)."""
    instrs = [encode_slti(3, 1, 1)]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLTI true: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_slti_false(dut):
    """SLTI: x1=5, slti 3 → 0 (5 not < 3 signed)."""
    instrs = [encode_slti(3, 1, 3)]
    f, ra, rb = make_prog(instrs, regs={1: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"SLTI false: expected 0, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sltiu_true(dut):
    """SLTIU: x1=5, sltiu 10 → 1."""
    instrs = [encode_sltiu(3, 1, 10)]
    f, ra, rb = make_prog(instrs, regs={1: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SLTIU true: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_sltiu_false(dut):
    """SLTIU: x1=10, sltiu 5 → 0."""
    instrs = [encode_sltiu(3, 1, 5)]
    f, ra, rb = make_prog(instrs, regs={1: 10})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0, f"SLTIU false: expected 0, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_xori_basic(dut):
    """XORI: x1=0b1100, xori 0b1010 → 0b0110."""
    instrs = [encode_xori(3, 1, 0b1010)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b0110, f"XORI basic: expected 6, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_ori_basic(dut):
    """ORI: x1=0b1100, ori 0b1010 → 0b1110."""
    instrs = [encode_ori(3, 1, 0b1010)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b1110, f"ORI basic: expected 14, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_andi_basic(dut):
    """ANDI: x1=0b1100, andi 0b1010 → 0b1000."""
    instrs = [encode_andi(3, 1, 0b1010)]
    f, ra, rb = make_prog(instrs, regs={1: 0b1100})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0b1000, f"ANDI basic: expected 8, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_slli_basic(dut):
    """SLLI: x1=1, slli 4 → 16."""
    instrs = [encode_slli(3, 1, 4)]
    f, ra, rb = make_prog(instrs, regs={1: 1})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 16, f"SLLI basic: expected 16, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_slli_zero(dut):
    """SLLI: x1=0xABCD, slli 0 → 0xABCD."""
    instrs = [encode_slli(3, 1, 0)]
    f, ra, rb = make_prog(instrs, regs={1: 0xABCD})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xABCD, \
        f"SLLI zero: expected 0xABCD, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_srli_basic(dut):
    """SRLI: x1=0x80000000, srli 4 → 0x08000000."""
    instrs = [encode_srli(3, 1, 4)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x08000000, \
        f"SRLI basic: expected 0x08000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_srli_by_31(dut):
    """SRLI: x1=0x80000000, srli 31 → 1."""
    instrs = [encode_srli(3, 1, 31)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 1, f"SRLI by 31: expected 1, got {read_reg(dut, 3)}"


@cocotb.test()
async def test_srai_negative(dut):
    """SRAI: x1=0x80000000, srai 4 → 0xF8000000 (sign propagates)."""
    instrs = [encode_srai(3, 1, 4)]
    f, ra, rb = make_prog(instrs, regs={1: 0x80000000})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xF8000000, \
        f"SRAI negative: expected 0xF8000000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_srai_positive(dut):
    """SRAI: x1=0x00000080, srai 4 → 0x00000008 (no sign propagation)."""
    instrs = [encode_srai(3, 1, 4)]
    f, ra, rb = make_prog(instrs, regs={1: 0x00000080})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00000008, \
        f"SRAI positive: expected 0x00000008, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# U-type
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_lui_basic(dut):
    """LUI: lui x3, 0x12345 → x3=0x12345000."""
    instrs = [encode_lui(3, 0x12345)]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x12345000, \
        f"LUI basic: expected 0x12345000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lui_max(dut):
    """LUI: lui x3, 0xFFFFF → x3=0xFFFFF000."""
    instrs = [encode_lui(3, 0xFFFFF)]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFFF000, \
        f"LUI max: expected 0xFFFFF000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_auipc_at_pc0(dut):
    """AUIPC: auipc x3, 0x12345 at PC=0 → 0 + 0x12345000 = 0x12345000."""
    instrs = [encode_auipc(3, 0x12345)]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x12345000, \
        f"AUIPC at PC=0: expected 0x12345000, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_auipc_at_pc4(dut):
    """AUIPC: nop at 0x0000, auipc x3, 1 at 0x0004 → 0x0004 + 0x1000 = 0x1004."""
    # encode_auipc at PC=4 with imm20=1 → result = 4 + (1<<12) = 0x1004
    instrs = [encode_addi(0, 0, 0), encode_auipc(3, 1)]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x1004, \
        f"AUIPC at PC=4: expected 0x1004, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# x0 invariant
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_x0_write_ignored(dut):
    """Write to x0 is ignored; subsequent reads return 0."""
    instrs = [
        encode_addi(0, 0, 0x42),  # attempt to write x0 = 0x42 (must be ignored)
        encode_addi(1, 0, 7),     # x1 = 0 + 7 = 7 (uses x0 as source; must be 0)
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 0) == 0, \
        f"x0 write ignored: x0 should remain 0, got 0x{read_reg(dut, 0):08x}"
    assert read_reg(dut, 1) == 7, \
        f"x0 write ignored: x1 should be 7, got {read_reg(dut, 1)}"


# ═════════════════════════════════════════════════════════════════════════════
# Sequential register dependency chain
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_reg_dep_chain(dut):
    """x1=1, then 4x addi x1,x1,1 → x1=5 (tests back-to-back RAW hazards)."""
    instrs = [
        encode_addi(1, 0, 1),  # x1 = 1
        encode_addi(1, 1, 1),  # x1 = 2
        encode_addi(1, 1, 1),  # x1 = 3
        encode_addi(1, 1, 1),  # x1 = 4
        encode_addi(1, 1, 1),  # x1 = 5
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 1) == 5, \
        f"Reg dep chain: expected x1=5, got {read_reg(dut, 1)}"


# ═════════════════════════════════════════════════════════════════════════════
# Load-use coherence
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_load_use(dut):
    """LW x3 from mem=0x55, then ADD x4=x3+x3 → x4=0xAA (load-use hazard)."""
    instrs = [
        encode_addi(1, 0, 4),   # x1 = 4 (data address)
        encode_lw(3, 1, 0),     # x3 = mem[4] = 0x55
        encode_add(4, 3, 3),    # x4 = x3 + x3 = 0xAA
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x55})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 4) == 0xAA, \
        f"Load-use: expected x4=0xAA, got 0x{read_reg(dut, 4):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Branches — taken
# Program structure:
#   0x00: addi x1, x0, v1       (setup)
#   0x04: addi x2, x0, v2       (setup)
#   0x08: branch x1, x2, +8    (if taken → 0x10)
#   0x0C: addi x3, x0, 0xFF    (skipped when taken)
#   0x10: addi x3, x0, 0x42    (target sentinel)
# halt loop appended by make_prog at 0x14
# ═════════════════════════════════════════════════════════════════════════════

def _make_branch_taken_prog(v1, v2, branch_instr):
    instrs = [
        encode_addi(1, 0, v1),       # 0x00
        encode_addi(2, 0, v2),       # 0x04
        branch_instr,                 # 0x08  branch +8 → 0x10
        encode_addi(3, 0, 0xFF),     # 0x0C  (must be skipped)
        encode_addi(3, 0, 0x42),     # 0x10  (branch target)
    ]
    return instrs


@cocotb.test()
async def test_beq_taken(dut):
    """BEQ taken: x1==x2 (17==17) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 17, encode_beq(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BEQ taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bne_taken(dut):
    """BNE taken: x1!=x2 (17!=16) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 16, encode_bne(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BNE taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_blt_taken(dut):
    """BLT taken: x1<x2 signed (17<20) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 20, encode_blt(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BLT taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bge_taken(dut):
    """BGE taken: x1>=x2 signed (17>=16) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 16, encode_bge(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BGE taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bltu_taken(dut):
    """BLTU taken: x1<x2 unsigned (17<20) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 20, encode_bltu(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BLTU taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bgeu_taken(dut):
    """BGEU taken: x1>=x2 unsigned (17>=16) → x3=0x42."""
    instrs = _make_branch_taken_prog(17, 16, encode_bgeu(1, 2, 8))
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BGEU taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


# ═════════════════════════════════════════════════════════════════════════════
# Branches — not taken
# Program structure:
#   0x00: branch x1, x2, +8    (NOT taken → fall through)
#   0x04: addi x3, x0, 0x42   (fall-through sentinel)
# halt loop at 0x08.
# If accidentally taken → jumps to halt at 0x08, x3 stays 0.
# Pre-load registers via regs={} to avoid ADDI setup instructions.
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_beq_not_taken(dut):
    """BEQ not taken: x1=1, x2=2 (1≠2 → not taken) → fall-through x3=0x42."""
    instrs = [
        encode_beq(1, 2, 8),        # 0x00  NOT taken (1≠2)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 1, 2: 2})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BEQ not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bne_not_taken(dut):
    """BNE not taken: x1=5, x2=5 (equal → not taken) → fall-through x3=0x42."""
    instrs = [
        encode_bne(1, 2, 8),        # 0x00  NOT taken (5==5)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 5, 2: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BNE not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_blt_not_taken(dut):
    """BLT not taken: x1=10, x2=5 (10≥5 signed → not taken) → fall-through x3=0x42."""
    instrs = [
        encode_blt(1, 2, 8),        # 0x00  NOT taken (10 >= 5)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 10, 2: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BLT not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bge_not_taken(dut):
    """BGE not taken: x1=0xFFFFFFFF (-1), x2=0 (-1<0 signed → not taken for BGE)."""
    instrs = [
        encode_bge(1, 2, 8),        # 0x00  NOT taken (-1 < 0)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 0xFFFFFFFF, 2: 0})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BGE not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bltu_not_taken(dut):
    """BLTU not taken: x1=10, x2=5 (10≥5 unsigned → not taken)."""
    instrs = [
        encode_bltu(1, 2, 8),       # 0x00  NOT taken (10 >= 5 unsigned)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 10, 2: 5})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BLTU not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_bgeu_not_taken(dut):
    """BGEU not taken: x1=5, x2=10 (5<10 unsigned → not taken)."""
    instrs = [
        encode_bgeu(1, 2, 8),       # 0x00  NOT taken (5 < 10 unsigned)
        encode_addi(3, 0, 0x42),    # 0x04  fall-through
    ]
    f, ra, rb = make_prog(instrs, regs={1: 5, 2: 10})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x42, \
        f"BGEU not taken: expected x3=0x42, got 0x{read_reg(dut, 3):02x}"


# ═════════════════════════════════════════════════════════════════════════════
# JAL / JALR
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_jal(dut):
    """
    0x00: jal x5, +8    → x5=4 (PC+4), PC jumps to 0x08
    0x04: addi x3,0,0xFF (skipped)
    0x08: addi x3,0,0x42 (executed — jump target)
    halt at 0x0C (appended by make_prog)
    """
    instrs = [
        encode_jal(5, 8),            # 0x00  jal x5, +8
        encode_addi(3, 0, 0xFF),     # 0x04  skipped
        encode_addi(3, 0, 0x42),     # 0x08  target
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == 4, \
        f"JAL: expected x5=4 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, \
        f"JAL: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_jalr_zero_imm(dut):
    """
    0x00: addi x1,0,12  → x1=12
    0x04: jalr x5,x1,0  → x5=8, PC=(12+0)&~1=12
    0x08: addi x3,0,0xFF (skipped)
    0x0C: addi x3,0,0x42 (target)
    halt at 0x10 (appended by make_prog)
    """
    instrs = [
        encode_addi(1, 0, 12),       # 0x00
        encode_jalr(5, 1, 0),        # 0x04  → PC=12, x5=8
        encode_addi(3, 0, 0xFF),     # 0x08  skipped
        encode_addi(3, 0, 0x42),     # 0x0C  target
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == 8, \
        f"JALR zero imm: expected x5=8 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, \
        f"JALR zero imm: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_jalr_nonzero_imm(dut):
    """
    0x00: addi x1,0,8   → x1=8
    0x04: jalr x5,x1,4  → x5=8, PC=(8+4)&~1=12
    0x08: addi x3,0,0xFF (skipped)
    0x0C: addi x3,0,0x42 (target)
    halt at 0x10 (appended by make_prog)
    """
    instrs = [
        encode_addi(1, 0, 8),        # 0x00
        encode_jalr(5, 1, 4),        # 0x04  → PC=12, x5=8
        encode_addi(3, 0, 0xFF),     # 0x08  skipped
        encode_addi(3, 0, 0x42),     # 0x0C  target
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == 8, \
        f"JALR nonzero imm: expected x5=8 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, \
        f"JALR nonzero imm: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"


@cocotb.test()
async def test_jalr_clear_lsb(dut):
    """
    0x00: addi x1,0,13  → x1=13 (odd)
    0x04: jalr x5,x1,0  → x5=8, PC=(13+0)&~1=12
    0x08: addi x3,0,0xFF (skipped)
    0x0C: addi x3,0,0x42 (target — LSB cleared correctly)
    halt at 0x10 (appended by make_prog)
    """
    instrs = [
        encode_addi(1, 0, 13),       # 0x00
        encode_jalr(5, 1, 0),        # 0x04  → PC=12 (13&~1), x5=8
        encode_addi(3, 0, 0xFF),     # 0x08  skipped
        encode_addi(3, 0, 0x42),     # 0x0C  target
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == 8, \
        f"JALR clear LSB: expected x5=8 (link), got {read_reg(dut, 5)}"
    assert read_reg(dut, 3) == 0x42, \
        f"JALR clear LSB: expected x3=0x42 (target), got 0x{read_reg(dut, 3):02x}"


# ═════════════════════════════════════════════════════════════════════════════
# Memory — word
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_lw_basic(dut):
    """LW: pre-load data[4]=0x12345678; addi x1=4; lw x3,0(x1) → x3=0x12345678."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4
        encode_lw(3, 1, 0),          # x3 = mem[4]
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x12345678})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x12345678, \
        f"LW basic: expected 0x12345678, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sw_basic(dut):
    """SW: addi x1=4 (addr), addi x2=0x55 (val); sw x2,0(x1) → ram_b[4]=0x55."""
    instrs = [
        encode_addi(2, 0, 0x55),     # x2 = 0x55 (value)
        encode_addi(1, 0, 4),        # x1 = 4 (address)
        encode_sw(1, 2, 0),          # mem[x1+0] = x2
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_mem(dut, 4) == 0x55, \
        f"SW basic: expected ram_b[4]=0x55, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sw_then_lw(dut):
    """SW then LW: store 0xDEADBEEF at addr 4, load it back → x3=0xDEADBEEF."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4 (address)
        encode_sw(1, 2, 0),          # mem[4] = x2 (pre-loaded via regs)
        encode_lw(3, 1, 0),          # x3 = mem[4]
    ]
    f, ra, rb = make_prog(instrs, regs={2: 0xDEADBEEF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xDEADBEEF, \
        f"SW then LW: expected 0xDEADBEEF, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Memory — byte loads
# Data word 0x807F01FF at addr 4 (little-endian view):
#   bits[ 7: 0] = 0xFF  (byte at addr 4, offset 0)
#   bits[15: 8] = 0x01  (byte at addr 5, offset 1)
#   bits[23:16] = 0x7F  (byte at addr 6, offset 2)
#   bits[31:24] = 0x80  (byte at addr 7, offset 3)
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_lb_off0(dut):
    """LB at addr 4 (offset 0): byte=0xFF → sign-ext 0xFFFFFFFF."""
    instrs = [
        encode_addi(1, 0, 4),
        encode_lb(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFFFFFF, \
        f"LB off0: expected 0xFFFFFFFF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lb_off1(dut):
    """LB at addr 5 (offset 1): byte=0x01 → sign-ext 0x00000001."""
    instrs = [
        encode_addi(1, 0, 5),
        encode_lb(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00000001, \
        f"LB off1: expected 0x00000001, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lb_off2(dut):
    """LB at addr 6 (offset 2): byte=0x7F → sign-ext 0x0000007F."""
    instrs = [
        encode_addi(1, 0, 6),
        encode_lb(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x0000007F, \
        f"LB off2: expected 0x0000007F, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lb_off3(dut):
    """LB at addr 7 (offset 3): byte=0x80 → sign-ext 0xFFFFFF80."""
    instrs = [
        encode_addi(1, 0, 7),
        encode_lb(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFFFF80, \
        f"LB off3: expected 0xFFFFFF80, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lbu_off0(dut):
    """LBU at addr 4 (offset 0): byte=0xFF → zero-ext 0x000000FF."""
    instrs = [
        encode_addi(1, 0, 4),
        encode_lbu(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x000000FF, \
        f"LBU off0: expected 0x000000FF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lbu_off3(dut):
    """LBU at addr 7 (offset 3): byte=0x80 → zero-ext 0x00000080."""
    instrs = [
        encode_addi(1, 0, 7),
        encode_lbu(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00000080, \
        f"LBU off3: expected 0x00000080, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Memory — halfword loads
# Data word 0x7FFF8001 at addr 4:
#   bits[15: 0] = 0x8001  (halfword at addr 4, bit[1]=0)
#   bits[31:16] = 0x7FFF  (halfword at addr 6, bit[1]=1)
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_lh_negative(dut):
    """LH at addr 4: halfword=0x8001 → sign-ext 0xFFFF8001."""
    instrs = [
        encode_addi(1, 0, 4),
        encode_lh(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x7FFF8001})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xFFFF8001, \
        f"LH negative: expected 0xFFFF8001, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lh_positive(dut):
    """LH at addr 6: halfword=0x7FFF → sign-ext 0x00007FFF."""
    instrs = [
        encode_addi(1, 0, 6),
        encode_lh(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x7FFF8001})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00007FFF, \
        f"LH positive: expected 0x00007FFF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lhu_hi_bit(dut):
    """LHU at addr 4: halfword=0x8001 → zero-ext 0x00008001."""
    instrs = [
        encode_addi(1, 0, 4),
        encode_lhu(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x7FFF8001})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00008001, \
        f"LHU hi bit: expected 0x00008001, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_lhu_positive(dut):
    """LHU at addr 6: halfword=0x7FFF → zero-ext 0x00007FFF."""
    instrs = [
        encode_addi(1, 0, 6),
        encode_lhu(3, 1, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x7FFF8001})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0x00007FFF, \
        f"LHU positive: expected 0x00007FFF, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Sub-word stores
# Old word = 0x11223344 at addr 4.  Store value = 0xAA (SB) or 0x7AB (SH).
# SB little-endian merge:
#   off0: {old[31:8],  0xAA}              = 0x112233AA
#   off1: {old[31:16], 0xAA, old[7:0]}    = 0x1122AA44
#   off2: {old[31:24], 0xAA, old[15:0]}   = 0x11AA3344
#   off3: {0xAA, old[23:0]}               = 0xAA223344
# SH little-endian merge (store 0x7AB):
#   off0 (bit[1]=0): {old[31:16], 0x07AB} = 0x112207AB
#   off2 (bit[1]=1): {0x07AB, old[15:0]}  = 0x07AB3344
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_sb_off0(dut):
    """SB: store 0xAA at byte offset 0 of 0x11223344 → 0x112233AA."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4 (byte addr, offset 0)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),          # mem[4] byte 0 = 0xAA
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0x112233AA, \
        f"SB off0: expected 0x112233AA, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sb_off1(dut):
    """SB: store 0xAA at byte offset 1 of 0x11223344 → 0x1122AA44."""
    instrs = [
        encode_addi(1, 0, 5),        # x1 = 5 (byte addr, offset 1)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0x1122AA44, \
        f"SB off1: expected 0x1122AA44, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sb_off2(dut):
    """SB: store 0xAA at byte offset 2 of 0x11223344 → 0x11AA3344."""
    instrs = [
        encode_addi(1, 0, 6),        # x1 = 6 (byte addr, offset 2)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0x11AA3344, \
        f"SB off2: expected 0x11AA3344, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sb_off3(dut):
    """SB: store 0xAA at byte offset 3 of 0x11223344 → 0xAA223344."""
    instrs = [
        encode_addi(1, 0, 7),        # x1 = 7 (byte addr, offset 3)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0xAA223344, \
        f"SB off3: expected 0xAA223344, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sh_off0(dut):
    """SH: store 0x7AB at halfword offset 0 (bit[1]=0) of 0x11223344 → 0x112207AB."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4 (bit[1]=0)
        encode_addi(2, 0, 0x7AB),    # x2 = 0x07AB
        encode_sh(1, 2, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0x112207AB, \
        f"SH off0: expected 0x112207AB, got 0x{read_mem(dut, 4):08x}"


@cocotb.test()
async def test_sh_off2(dut):
    """SH: store 0x7AB at halfword offset 2 (bit[1]=1) of 0x11223344 → 0x07AB3344."""
    instrs = [
        encode_addi(1, 0, 6),        # x1 = 6 (bit[1]=1)
        encode_addi(2, 0, 0x7AB),    # x2 = 0x07AB
        encode_sh(1, 2, 0),
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_mem(dut, 4) == 0x07AB3344, \
        f"SH off2: expected 0x07AB3344, got 0x{read_mem(dut, 4):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Memory coherence
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_sw_lw_coherence(dut):
    """SW then LW: write 0xDEADBEEF via SW, read back via LW → same value."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4 (address)
        encode_sw(1, 2, 0),          # mem[4] = x2 (pre-loaded)
        encode_lw(3, 1, 0),          # x3 = mem[4]
    ]
    f, ra, rb = make_prog(instrs, regs={2: 0xDEADBEEF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 3) == 0xDEADBEEF, \
        f"SW/LW coherence: expected 0xDEADBEEF, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sb_lbu_coherence(dut):
    """SB at off0 then LBU from off0: pre-load 0x11223344, SB 0xAA → LBU=0xAA."""
    instrs = [
        encode_addi(1, 0, 4),        # x1 = 4 (byte addr, offset 0)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),          # mem[4] byte 0 = 0xAA
        encode_lbu(3, 1, 0),         # x3 = zero-ext(mem[4] byte 0)
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_reg(dut, 3) == 0xAA, \
        f"SB/LBU coherence: expected 0xAA, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_sh_lhu_coherence(dut):
    """SH at off2 then LHU from off2: pre-load 0x11223344, SH 0x7AB → LHU=0x7AB."""
    instrs = [
        encode_addi(1, 0, 6),        # x1 = 6 (halfword addr, bit[1]=1)
        encode_addi(2, 0, 0x7AB),    # x2 = 0x07AB
        encode_sh(1, 2, 0),          # mem[6] hw = 0x07AB
        encode_lhu(3, 1, 0),         # x3 = zero-ext(mem[6] hw)
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    assert read_reg(dut, 3) == 0x7AB, \
        f"SH/LHU coherence: expected 0x7AB, got 0x{read_reg(dut, 3):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# Alignment traps
# Pattern: instrs=[*setup, trap_instr]; trap_epc = len(setup)*4
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_align_lh_odd(dut):
    """LH at odd addr 5 → load-address-misaligned trap (cause=4, tval=5)."""
    setup = [encode_addi(1, 0, 5)]
    trap_instr = encode_lh(3, 1, 0)
    instrs = setup + [trap_instr]
    trap_epc = len(setup) * 4
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"LH misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    check_trap(dut, cause=4, tval=5, epc=trap_epc)


@cocotb.test()
async def test_align_lhu_odd(dut):
    """LHU at odd addr 5 → load-address-misaligned trap (cause=4, tval=5)."""
    setup = [encode_addi(1, 0, 5)]
    trap_instr = encode_lhu(3, 1, 0)
    instrs = setup + [trap_instr]
    trap_epc = len(setup) * 4
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"LHU misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    check_trap(dut, cause=4, tval=5, epc=trap_epc)


@cocotb.test()
async def test_align_lw_two(dut):
    """LW at addr 6 (not 4-byte aligned) → load-address-misaligned trap (cause=4, tval=6)."""
    setup = [encode_addi(1, 0, 6)]
    trap_instr = encode_lw(3, 1, 0)
    instrs = setup + [trap_instr]
    trap_epc = len(setup) * 4
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"LW misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    check_trap(dut, cause=4, tval=6, epc=trap_epc)


@cocotb.test()
async def test_align_sh_odd(dut):
    """SH at odd addr 5 → store-address-misaligned trap (cause=6, tval=5)."""
    setup = [encode_addi(1, 0, 5)]
    trap_instr = encode_sh(1, 2, 0)
    instrs = setup + [trap_instr]
    trap_epc = len(setup) * 4
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"SH misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    check_trap(dut, cause=6, tval=5, epc=trap_epc)


@cocotb.test()
async def test_align_sw_two(dut):
    """SW at addr 6 (not 4-byte aligned) → store-address-misaligned trap (cause=6, tval=6)."""
    setup = [encode_addi(1, 0, 6)]
    trap_instr = encode_sw(1, 2, 0)
    instrs = setup + [trap_instr]
    trap_epc = len(setup) * 4
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"SW misalign: trap handler not reached; x5={read_reg(dut, 5):#x}"
    check_trap(dut, cause=6, tval=6, epc=trap_epc)


@cocotb.test()
async def test_no_trap_lb_odd(dut):
    """LB at odd addr 5 does NOT trap; byte=0x01 (bits[15:8] of 0x807F01FF)."""
    instrs = [
        encode_addi(1, 0, 5),        # x1 = 5 (odd — but LB never traps)
        encode_lb(3, 1, 0),          # x3 = sign-ext(mem[5]) = 0x00000001
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x807F01FF})
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    check_trap(dut, valid=0)
    assert read_reg(dut, 3) == 0x00000001, \
        f"LB odd no trap: expected 0x00000001, got 0x{read_reg(dut, 3):08x}"


@cocotb.test()
async def test_no_trap_sb_odd(dut):
    """SB at odd addr 5 does NOT trap; performs RMW; byte 1 of 0x11223344 → 0xAA."""
    instrs = [
        encode_addi(1, 0, 5),        # x1 = 5 (odd — but SB never traps)
        encode_addi(2, 0, 0xAA),     # x2 = 0xAA
        encode_sb(1, 2, 0),          # mem[4] byte 1 = 0xAA → 0x1122AA44
    ]
    f, ra, rb = make_prog(instrs, data={4: 0x11223344})
    await run_test(dut, f, ra, rb, budget(len(instrs), n_rmw=1))
    check_trap(dut, valid=0)
    assert read_mem(dut, 4) == 0x1122AA44, \
        f"SB odd no trap: expected 0x1122AA44, got 0x{read_mem(dut, 4):08x}"


# ═════════════════════════════════════════════════════════════════════════════
# FENCE
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_fence(dut):
    """FENCE acts as NOP: execution continues, x2=3, no trap."""
    instrs = [
        encode_addi(1, 0, 1),        # x1 = 1
        encode_fence(),               # FENCE (NOP semantics)
        encode_addi(2, 1, 2),        # x2 = x1 + 2 = 3
    ]
    f, ra, rb = make_prog(instrs)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 2) == 3, \
        f"FENCE: expected x2=3, got {read_reg(dut, 2)}"
    check_trap(dut, valid=0)


# ═════════════════════════════════════════════════════════════════════════════
# ECALL / EBREAK
# ═════════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_ecall(dut):
    """
    ECALL at PC=0 → redirect to TRAP_VECTOR; x3 at 0x0004 NOT executed.
    trap_cause=11 (machine-mode ECALL), trap_epc=0.
    """
    instrs = [
        encode_ecall(),              # 0x00  ECALL → trap
        encode_addi(3, 0, 0xFF),    # 0x04  must NOT execute
    ]
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"ECALL: trap handler not reached; x5={read_reg(dut, 5):#x}"
    assert read_reg(dut, 3) == 0, \
        f"ECALL: instruction after trap must not execute; x3={read_reg(dut, 3):#x}"
    check_trap(dut, valid=1, cause=11, epc=0)


@cocotb.test()
async def test_ebreak(dut):
    """
    EBREAK at PC=0 → redirect to TRAP_VECTOR.
    trap_cause=3, trap_epc=0.
    """
    instrs = [
        encode_ebreak(),             # 0x00  EBREAK → trap
        encode_addi(3, 0, 0xFF),    # 0x04  must NOT execute
    ]
    f, ra, rb = make_prog(instrs, trap_handler=True)
    await run_test(dut, f, ra, rb, budget(len(instrs)))
    assert read_reg(dut, 5) == TRAP_SENTINEL, \
        f"EBREAK: trap handler not reached; x5={read_reg(dut, 5):#x}"
    assert read_reg(dut, 3) == 0, \
        f"EBREAK: instruction after trap must not execute; x3={read_reg(dut, 3):#x}"
    check_trap(dut, valid=1, cause=3, epc=0)
