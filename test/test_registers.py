import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles

@cocotb.test()
async def test_registers(reg):
    clock = Clock(reg.clk, 4, units="ns")
    cocotb.start_soon(clock.start())

    #reset
    reg.reset.value = 1
    await ClockCycles(reg.clk, 1)
    reg.reset.value = 0

    #write values
    reg.w_data.value = 0x0000_0001
    reg.rd.value = 0x0000_0001
    reg.w_en.value = 0b1
    await ClockCycles(reg.clk, 1)

    #read that value
    reg.rs1.value = 0x0000_0001
    await ClockCycles(reg.clk, 1)

    assert reg.rdata_1.value == 0x0000_0001