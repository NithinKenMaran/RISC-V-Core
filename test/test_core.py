import cocotb
from cocotb.clock import Clock

@cocotb.test()
async def test_add(core):
    clock = Clock(core.clk, 4, units="ns")
    cocotb.start_soon(clock.start())