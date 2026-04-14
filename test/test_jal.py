import cocotb
from cocotb.triggers import RisingEdge, Timer

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "include"))

from include.encode import *
from include.test_helpers import *


def imem_read(imem, byte_addr):
    word_addr = byte_addr >> 2
    return imem[word_addr]


@cocotb.test()
async def test_jal(core):
    """
    Program layout:
      0: addi x1, x0, 10
      1: jal  x5, +8        -> jump to instruction 3, x5 = PC+4 = 8
      2: addi x2, x0, 99    -> skipskip
      3: addi x2, x0, 88    -> execute
    """

    imem = {
        0: encode_addi(1, 0, 10),  # x1 = 10
        1: encode_jal(5, 8),       # x5 = 8, jump from PC=4 to PC=12
        2: encode_addi(2, 0, 99),  # skipskip
        3: encode_addi(2, 0, 88),  # execute
    }

    await init_core(core)
    core.instr_valid.value = 1

    # -------- instr 0 --------
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[1].value)
    assert got == 10, f"x1 wrong: got {got}, expected 10"

    # -------- instr 1: jal --------
    pc = int(core.pc.value)
    assert pc == 4, f"Before jal, expected pc=4, got {pc}"

    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    # jal at PC=4 should write PC+4 = 8 into rd=x5
    got = int(core.register_file.registers[5].value)
    assert got == 8, f"x5 wrong after jal: got {got}, expected 8"

    # After jal +8 from PC=4, next PC should be 12 (instruction index 3)
    pc = int(core.pc.value)
    assert pc == 12, f"After jal, expected pc=12, got {pc}"

    # -------- instr 3 --------
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[2].value)
    assert got == 88, f"x2 wrong: got {got}, expected 88"

    # Optional sanity: make sure skipped instruction did not run first
    assert got != 99, "JAL did not skip the instruction at PC=8"