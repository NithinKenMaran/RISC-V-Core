import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from include.encode import encode_add

@cocotb.test()
async def test_add(core):
    cocotb.start_soon(Clock(core.clk, 4, units="ns").start())

    core.reset.value = 1
    core.instr_valid.value = 0
    core.instr.value = 0

    await RisingEdge(core.clk)
    await RisingEdge(core.clk)
    core.reset.value = 0
    await Timer(1, units="ns")

    # can seed values into register file directly
    core.register_file.registers[1].value = 10
    core.register_file.registers[2].value = 20
    await Timer(1, units="ns")

    # INSTRUCTION ENCODE HAPPENS HERE
    core.instr.value = encode_add(rd=3, rs1=1, rs2=2)
    # ###############################

    core.instr_valid.value = 1
    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    assert int(core.register_file.registers[3].value) == 30, (
        f"x3 wrong: got {int(core.register_file.registers[3].value)}, expected 30"
    )

    assert int(core.register_file.registers[1].value) == 10
    assert int(core.register_file.registers[2].value) == 20