import cocotb

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "include"))

from include.test_helpers import *

mem = {
    24 : 0x100
}

@cocotb.test()
async def test_lw(core):
    await init_core(core)

    core.instr.value = encode_addi(1, 0, 16)
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[1].value)
    assert got == 16, f"x1 wrong: got 0x{got:08x}, expected 0x00000010"

    core.instr.value = encode_lw(5, 1, 8) 
    
    
    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    print(f"reached last assertion. reg_write = {core.reg_write.value}, reg_wdata = {core.reg_w_data.value}, mem_addr = {core.mem_addr.value}, mem_rdata = {core.mem_rdata.value}")

    got = int(core.register_file.registers[5].value)
    assert got == 0x100, f"x5 wrong: got 0x{got:08x}, expected 0x00000100, reg_write = {core.reg_write.value}, reg_wdata = {core.reg_wdata.value}, mem_addr = {core.mem_addr.value}, mem_rdata = {core.mem_rdata.value}"
