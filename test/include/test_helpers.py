import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def u32(x: int) -> int:
    return x & 0xFFFFFFFF


def sext(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


async def init_core(core):
    cocotb.start_soon(Clock(core.clk, 4, units="ns").start())
    core.reset.value = 1
    core.instr_valid.value = 0
    core.instr.value = 0

    await RisingEdge(core.clk)
    await RisingEdge(core.clk)
    core.reset.value = 0
    await Timer(1, units="ns")


async def run_rtype(core, encode_fn, a, b, expected, rd=3, rs1=1, rs2=2):
    await init_core(core)

    core.register_file.registers[rs1].value = u32(a)
    core.register_file.registers[rs2].value = u32(b)
    await Timer(1, units="ns")

    core.instr.value = encode_fn(rd=rd, rs1=rs1, rs2=rs2)
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[rd].value)
    assert got == u32(expected), f"x{rd} wrong: got 0x{got:08x}, expected 0x{u32(expected):08x}"

    assert int(core.register_file.registers[rs1].value) == u32(a)
    assert int(core.register_file.registers[rs2].value) == u32(b)


async def run_itype(core, encode_fn, a, imm, expected, rd=3, rs1=1, is_shift=False):
    await init_core(core)

    core.register_file.registers[rs1].value = u32(a)
    await Timer(1, units="ns")

    if is_shift:
        core.instr.value = encode_fn(rd=rd, rs1=rs1, shamt=imm)
    else:
        core.instr.value = encode_fn(rd=rd, rs1=rs1, imm=imm)

    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[rd].value)
    assert got == u32(expected), f"x{rd} wrong: got 0x{got:08x}, expected 0x{u32(expected):08x}"

    assert int(core.register_file.registers[rs1].value) == u32(a)