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
    imem = { 
        0: encode_addi(1, 0, 10),   # x1 = 10
        1: encode_addi(2, 0, 7),    # x2 = 7
        2: encode_add(3, 1, 2),     # x3 = 17
        3: encode_addi(4, 0, 17),    # x4 = 17
        4: encode_beq(3, 4, 8),     # if x3 == x4, pc += 8
        5: encode_addi(5, 0, 99),   # x5 = 99 (hopefully will skip)
        6: encode_addi(5, 0, 88),   # x5 = 88
    }

    await init_core(core) # holds reset for 2 clock edges, then turns off reset, waits 1 ns, and returns

    ###### x1 = 10 ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[1].value)
    assert got == 10, f"x1 wrong: got {got}, expected 10"

    ##### x2 = 7 ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[2].value)
    assert got == 7, f"x2 wrong: got {got}, expected 7, \n \
        pc={pc}, instr=0x{instr:08x}"

    ###### x3 = 17 ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[3].value)
    assert got == 17, f"x3 wrong: got {got}, expected 17, \n \
        pc={pc}, instr=0x{instr:08x}"
    
    ##### x4 = 17 ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[4].value)
    assert got == 17, f"x4 wrong: got {got}, expected 17, \n \
        pc={pc}, instr=0x{instr:08x}"

    ##### beq ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    ##### x5 = 88 (skipped x5 = 99) ######
    pc = int(core.pc.value)
    instr = imem_read(imem, pc)
    core.instr.value = instr

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[5].value)
    assert got == 88, f"x5 wrong: got {got}, expected 88, \n \
        pc={pc}, instr=0x{instr:08x}"

    print(f"Final PC: {pc}, x5 value: {got}")