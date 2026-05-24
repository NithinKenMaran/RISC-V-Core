import cocotb

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "include"))

from include.test_helpers import *


@cocotb.test()
async def test_lui(core):
    await init_core(core)

    core.instr.value = encode_lui(5, 0x12345)
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[5].value)
    assert got == 0x12345000, f"x5 wrong: got 0x{got:08x}, expected 0x12345000"

@cocotb.test()
async def test_auipc(core):
    await init_core(core)

    core.instr.value = encode_auipc(5, 0x12345)
    core.instr_valid.value = 1

    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    got = int(core.register_file.registers[5].value)
    expected = 0x12345000
    assert got == expected, f"x5 wrong: got 0x{got:08x}, expected 0x{expected:08x}"