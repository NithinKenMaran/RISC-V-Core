import cocotb

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "include"))

from include.test_helpers import *


@cocotb.test()
async def test_jalr(core):
    """
    Program layout:
      0: addi x1, x0, base
      1: jalr x5, x1, imm
      2: addi x2, x0, 99   #skipskip
      3: addi x2, x0, 88   #execute
    """


    await run_jalr_test(
        core,
        base=13,
        imm=-1,
        expected_target=12,
        expected_rd=8,
        rd=5,
        rs1=1,
    )
