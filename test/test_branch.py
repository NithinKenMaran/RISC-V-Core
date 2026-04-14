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
async def test_beq(core):
    await run_branch_test(
        core,
        branch_instr=encode_beq(3, 4, 8),   # 17 == 17 -> taken
        x3_expected=17,
        x4_expected=17,
    )


@cocotb.test()
async def test_bne(core):
    await run_branch_test(
        core,
        branch_instr=encode_bne(3, 4, 8),   # 17 != 16 -> taken
        x3_expected=17,
        x4_expected=16,
    )


@cocotb.test()
async def test_blt(core):
    await run_branch_test(
        core,
        branch_instr=encode_blt(3, 4, 8),   # 17 < 20 -> taken
        x3_expected=17,
        x4_expected=20,
    )


@cocotb.test()
async def test_bge(core):
    await run_branch_test(
        core,
        branch_instr=encode_bge(3, 4, 8),   # 17 >= 16 -> taken
        x3_expected=17,
        x4_expected=16,
    )


@cocotb.test()
async def test_bltu(core):
    await run_branch_test(
        core,
        branch_instr=encode_bltu(3, 4, 8),  # 17 < 20 unsigned -> taken
        x3_expected=17,
        x4_expected=20,
    )


@cocotb.test()
async def test_bgeu(core):
    await run_branch_test(
        core,
        branch_instr=encode_bgeu(3, 4, 8),  # 17 >= 16 unsigned -> taken
        x3_expected=17,
        x4_expected=16,
    )