# test/test_qspi_add.py

import os
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge

# Make test/include importable regardless of where cocotb launched from.
TEST_DIR = Path(__file__).resolve().parent
INCLUDE_DIR = TEST_DIR / "include"
sys.path.insert(0, str(INCLUDE_DIR))

from mem_image import (
    MemoryImage,
    reg_addr,
    load_images_into_pmod,
    read_word_from_pmod_array,
)
from qspi_host import start_system_clock, wait_core_cycles
from qspi_init import init_qspi_pmod
from riscv_encode import encode_add, encode_nop


def build_add_images():
    """
    Program:
        add x3, x1, x2
        nop
        nop

    Initial external register file:
        x1 = 10
        x2 = 20

    Expected:
        x3 = 30
    """
    flash = MemoryImage()
    rama = MemoryImage()
    ramb = MemoryImage()

    flash.set_word_qspi(0x0000, encode_add(rd=3, rs1=1, rs2=2))
    flash.set_word_qspi(0x0004, encode_nop())
    flash.set_word_qspi(0x0008, encode_nop())

    rama.set_word_qspi(reg_addr(1), 10)
    rama.set_word_qspi(reg_addr(2), 20)
    rama.set_word_qspi(reg_addr(3), 0xDEADBEEF)

    return flash, rama, ramb


@cocotb.test()
async def test_qspi_add(dut):
    # Phase 0: build per-test memory files.
    flash, rama, ramb = build_add_images()

    mem_dir = TEST_DIR / "mem"
    flash.write_hex(mem_dir / "flash.hex")
    rama.write_hex(mem_dir / "rama.hex")
    ramb.write_hex(mem_dir / "ramb.hex")

    # The Verilog model's initial $readmemh happens before this coroutine,
    # so mirror the images into the PMOD arrays as well.
    await load_images_into_pmod(dut, flash, rama, ramb)

    # Phase A: board-style RP2040/QSPI PMOD initialization.
    await start_system_clock(dut, period_ns=10)
    await init_qspi_pmod(dut, strict=True)

    # Phase B: actual core test.
    # One ADD needs fetch + rs1 read + rs2 read + writeback over QSPI.
    # Give enough cycles for the externalized-state FSM and QSPI transfers.
    await wait_core_cycles(dut, 1200)

    x3 = read_word_from_pmod_array(dut.pmod.ram_a, reg_addr(3))
    assert x3 == 30, f"ADD failed: expected x3=30, got 0x{x3:08x}"

    # Sanity: x1/x2 unchanged.
    x1 = read_word_from_pmod_array(dut.pmod.ram_a, reg_addr(1))
    x2 = read_word_from_pmod_array(dut.pmod.ram_a, reg_addr(2))
    assert x1 == 10, f"x1 changed unexpectedly: 0x{x1:08x}"
    assert x2 == 20, f"x2 changed unexpectedly: 0x{x2:08x}"
