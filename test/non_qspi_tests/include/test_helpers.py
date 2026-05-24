import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from encode import *

def u32(x: int) -> int:
    return x & 0xFFFFFFFF

def imem_read(imem, byte_addr):
    word_addr = byte_addr >> 2
    return imem[word_addr]

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


async def run_branch_test(core, branch_instr, x3_expected, x4_expected):
    """
    Common branch test flow.

    Program layout:
      0: addi x1, x0, 10
      1: addi x2, x0, 7
      2: add  x3, x1, x2      -> x3 = 17
      3: addi x4, x0, <val>   -> x4 chosen per test
      4: branch x3, x4, +8
      5: addi x5, x0, 99      -> should be skipped if branch taken
      6: addi x5, x0, 88      -> should execute after taken branch
    """

    imem = {
        0: encode_addi(1, 0, 10),   # x1 = 10
        1: encode_addi(2, 0, 7),    # x2 = 7
        2: encode_add(3, 1, 2),     # x3 = 17
        3: encode_addi(4, 0, x4_expected),
        4: branch_instr,
        5: encode_addi(5, 0, 99),   # should be skipped
        6: encode_addi(5, 0, 88),   # should execute
    }

    await init_core(core)

    core.instr_valid.value = 1

    # Step through instructions 0..4
    for _ in range(5):
        pc = int(core.pc.value)
        instr = imem_read(imem, pc)
        core.instr.value = instr
        await RisingEdge(core.clk)
        await Timer(1, units="ns")

    got_x3 = int(core.register_file.registers[3].value)
    assert got_x3 == x3_expected, f"x3 wrong: got {got_x3}, expected {x3_expected}"

    got_x4 = int(core.register_file.registers[4].value)
    assert got_x4 == x4_expected, f"x4 wrong: got {got_x4}, expected {x4_expected}"

    # After the branch executes, fetch the instruction at the new PC
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got_x5 = int(core.register_file.registers[5].value)
    assert got_x5 == 88, (
        f"x5 wrong: got {got_x5}, expected 88\n"
        f"pc after branch={pc}, instr=0x{instr:08x}"
    )

async def run_jalr_test(core, base, imm, expected_target, expected_rd, rd=5, rs1=1):
    """
    Program layout:
      0: addi x1, x0, base
      1: jalr x5, x1, imm
      2: addi x2, x0, 99   -> skipp
      3: addi x2, x0, 88   -> execute

    """

    imem = {
        0: encode_addi(rs1, 0, base),      # x1 = base
        1: encode_jalr(rd, rs1, imm),      # rd = old pc + 4, pc = (x1 + imm) & ~1
        2: encode_addi(2, 0, 99),          # skipskip
        3: encode_addi(2, 0, 88),          # should execute
    }

    await init_core(core)
    core.instr_valid.value = 1

    # -------- instr 0 --------
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[rs1].value)
    assert got == u32(base), f"x{rs1} wrong: got {got}, expected {u32(base)}"
    print(f"x{rs1} = {got}")

    # -------- instr 1: jalr --------
    pc = int(core.pc.value)
    assert pc == 4, f"Before jalr, expected pc=4, got {pc}"
    print(f"PC before jalr: {pc}")

    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got_rd = int(core.register_file.registers[rd].value)
    assert got_rd == u32(expected_rd), (
        f"x{rd} wrong after jalr: got {got_rd}, expected {u32(expected_rd)}"
    )
    print(f"x{rd} after jalr: {got_rd}")

    pc = int(core.pc.value)
    assert pc == expected_target, f"After jalr, expected pc={expected_target}, got {pc}"
    print(f"PC after jalr: {pc}")

    # -------- target instr --------
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[2].value)
    assert got == 88, f"x2 wrong: got {got}, expected 88"
    print(f"x2 = {got}")
