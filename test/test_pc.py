import cocotb
from cocotb.clock import Clock
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
async def test_pc(core):
    imem = [
        encode_addi(1, 0, 10),   # x1 = 10
        encode_addi(2, 0, 7),    # x2 = 7
        encode_add(3, 1, 2),     # x3 = 17
        encode_andi(3, 3, 15),   # x3 = 17 & 15 = 1
    ]

    await init_core(core) # holds reset for 2 clock edges, then turns off reset, waits 1 ns, and returns

    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[1].value)
    assert got == 10, f"x1 wrong: got {got}, expected 10"

    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[2].value)
    assert got == 7, f"x2 wrong: got {got}, expected 7, \n \
        pc={pc}, instr=0x{instr:08x}"

    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[3].value)
    assert got == 17, f"x3 wrong: got {got}, expected 17, \n \
        pc={pc}, instr=0x{instr:08x}"
    
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[3].value)
    assert got == 1, f"x3 wrong: got {got}, expected 1, \n \
        pc={pc}, instr=0x{instr:08x}"