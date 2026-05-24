import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from include.encode import (
    encode_add,
    encode_sub,
    encode_sll,
    encode_slt,
    encode_sltu,
    encode_xor,
    encode_srl,
    encode_sra,
    encode_or,
    encode_and,
)

async def init_core(core):
    cocotb.start_soon(Clock(core.clk, 4, units="ns").start())
    core.reset.value = 1
    core.instr_valid.value = 0
    core.instr.value = 0

    await RisingEdge(core.clk)
    await RisingEdge(core.clk)
    core.reset.value = 0
    await Timer(1, units="ns")


async def test_op(core, encode_fn, a, b, expected, rd=3, rs1=1, rs2=2):

    # INITIALIZE CORE
    await init_core(core)

    # seed source registers directly
    core.register_file.registers[rs1].value = a
    core.register_file.registers[rs2].value = b
    await Timer(1, units="ns")

    # apply instruction
    core.instr.value = encode_fn(rd=rd, rs1=rs1, rs2=rs2)
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[rd].value)
    assert got == expected, f"x{rd} wrong: got {got}, expected {expected}"

    assert int(core.register_file.registers[rs1].value) == a
    assert int(core.register_file.registers[rs2].value) == b

@cocotb.test()
async def test_add(core):
    await test_op(core, encode_add, a=10, b=20, expected=30)


@cocotb.test()
async def test_sub(core):
    await test_op(core, encode_sub, a=20, b=10, expected=10)


@cocotb.test()
async def test_sll(core):
    await test_op(core, encode_sll, a=1, b=4, expected=16)


@cocotb.test()
async def test_slt_true(core):
    await test_op(core, encode_slt, a=5, b=10, expected=1)


@cocotb.test()
async def test_slt_false(core):
    await test_op(core, encode_slt, a=10, b=5, expected=0)


@cocotb.test()
async def test_slt_negative(core):
    await test_op(core, encode_slt, a=(0xFFFFFFFF), b=1, expected=1)  # -1 < 1


@cocotb.test()
async def test_sltu_true(core):
    await test_op(core, encode_sltu, a=5, b=10, expected=1)


@cocotb.test()
async def test_sltu_false(core):
    await test_op(core, encode_sltu, a=10, b=5, expected=0)


@cocotb.test()
async def test_sltu_unsigned(core):
    await test_op(core, encode_sltu, a=0xFFFFFFFF, b=1, expected=0)


@cocotb.test()
async def test_xor(core):
    await test_op(core, encode_xor, a=0b1100, b=0b1010, expected=0b0110)


@cocotb.test()
async def test_srl(core):
    await test_op(core, encode_srl, a=0x80000000, b=4, expected=0x08000000)


@cocotb.test()
async def test_sra(core):
    await test_op(core, encode_sra, a=0x80000000, b=4, expected=0xF8000000)


@cocotb.test()
async def test_or(core):
    await test_op(core, encode_or, a=0b1100, b=0b1010, expected=0b1110)


@cocotb.test()
async def test_and(core):
    await test_op(core, encode_and, a=0b1100, b=0b1010, expected=0b1000)