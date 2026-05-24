import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "include"))

from include.encode import *
from include.test_helpers import run_rtype, run_itype

# -----------------------------
# R-type tests
# -----------------------------
@cocotb.test()
async def test_rtype_add(core):
    await run_rtype(core, encode_add, a=10, b=20, expected=30)


@cocotb.test()
async def test_rtype_sub(core):
    await run_rtype(core, encode_sub, a=20, b=10, expected=10)


@cocotb.test()
async def test_rtype_sll(core):
    await run_rtype(core, encode_sll, a=1, b=4, expected=16)


@cocotb.test()
async def test_rtype_slt_true(core):
    await run_rtype(core, encode_slt, a=5, b=10, expected=1)


@cocotb.test()
async def test_rtype_slt_false(core):
    await run_rtype(core, encode_slt, a=10, b=5, expected=0)


@cocotb.test()
async def test_rtype_slt_negative(core):
    await run_rtype(core, encode_slt, a=0xFFFFFFFF, b=1, expected=1)  # -1 < 1


@cocotb.test()
async def test_rtype_sltu_true(core):
    await run_rtype(core, encode_sltu, a=5, b=10, expected=1)


@cocotb.test()
async def test_rtype_sltu_false(core):
    await run_rtype(core, encode_sltu, a=10, b=5, expected=0)


@cocotb.test()
async def test_rtype_sltu_unsigned(core):
    await run_rtype(core, encode_sltu, a=0xFFFFFFFF, b=1, expected=0)


@cocotb.test()
async def test_rtype_xor(core):
    await run_rtype(core, encode_xor, a=0b1100, b=0b1010, expected=0b0110)


@cocotb.test()
async def test_rtype_srl(core):
    await run_rtype(core, encode_srl, a=0x80000000, b=4, expected=0x08000000)


@cocotb.test()
async def test_rtype_sra(core):
    await run_rtype(core, encode_sra, a=0x80000000, b=4, expected=0xF8000000)


@cocotb.test()
async def test_rtype_or(core):
    await run_rtype(core, encode_or, a=0b1100, b=0b1010, expected=0b1110)


@cocotb.test()
async def test_rtype_and(core):
    await run_rtype(core, encode_and, a=0b1100, b=0b1010, expected=0b1000)


# -----------------------------
# I-type tests
# -----------------------------
@cocotb.test()
async def test_itype_addi_positive(core):
    await run_itype(core, encode_addi, a=10, imm=7, expected=17)


@cocotb.test()
async def test_itype_addi_negative_imm(core):
    await run_itype(core, encode_addi, a=10, imm=-3, expected=7)


@cocotb.test()
async def test_itype_addi_negative_result(core):
    await run_itype(core, encode_addi, a=0, imm=-1, expected=0xFFFFFFFF)


@cocotb.test()
async def test_itype_slti_true(core):
    await run_itype(core, encode_slti, a=5, imm=10, expected=1)


@cocotb.test()
async def test_itype_slti_false(core):
    await run_itype(core, encode_slti, a=10, imm=5, expected=0)


@cocotb.test()
async def test_itype_slti_signed(core):
    await run_itype(core, encode_slti, a=0xFFFFFFFF, imm=1, expected=1)  # -1 < 1


@cocotb.test()
async def test_itype_sltiu_true(core):
    await run_itype(core, encode_sltiu, a=5, imm=10, expected=1)


@cocotb.test()
async def test_itype_sltiu_false(core):
    await run_itype(core, encode_sltiu, a=10, imm=5, expected=0)


@cocotb.test()
async def test_itype_sltiu_with_negative_imm(core):
    # imm = -1 sign-extends to 0xFFFFFFFF
    await run_itype(core, encode_sltiu, a=1, imm=-1, expected=1)


@cocotb.test()
async def test_itype_xori(core):
    await run_itype(core, encode_xori, a=0b1100, imm=0b1010, expected=0b0110)


@cocotb.test()
async def test_itype_ori(core):
    await run_itype(core, encode_ori, a=0b1100, imm=0b1010, expected=0b1110)


@cocotb.test()
async def test_itype_andi(core):
    await run_itype(core, encode_andi, a=0b1100, imm=0b1010, expected=0b1000)


@cocotb.test()
async def test_itype_slli(core):
    await run_itype(core, encode_slli, a=1, imm=4, expected=16, is_shift=True)


@cocotb.test()
async def test_itype_srli(core):
    await run_itype(core, encode_srli, a=0x80000000, imm=4, expected=0x08000000, is_shift=True)


@cocotb.test()
async def test_itype_srai(core):
    await run_itype(core, encode_srai, a=0x80000000, imm=4, expected=0xF8000000, is_shift=True)