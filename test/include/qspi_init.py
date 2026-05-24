# test/include/qspi_init.py
#
# Phase A init: emulates the TinyTapeout PCB/RP2040 configuring the QSPI PMOD
# before releasing control to the core.

from cocotb.triggers import Timer, RisingEdge
from qspi_host import QspiHost, CS_FLASH, CS_RAMA, CS_RAMB


async def hold_core_in_reset(dut):
    dut.reset.value = 1
    await Timer(1, units="ns")


async def release_core_reset(dut, reset_cycles=3):
    for _ in range(reset_cycles):
        await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)


async def init_qspi_pmod(dut, strict=True):
    """
    Phase A.

    strict=True:
        Drive board-style init transactions through the host pins:
          flash: leave continuous mode, then enter continuous-read mode
          RAM A/B: send 0x35 to enter QPI mode

    The current qspi_ctrl.v runtime flash protocol is:
          address -> dummy -> data
    so the PMOD model's flash_continuous_mode flag is what matters after init.
    """
    await hold_core_in_reset(dut)

    host = QspiHost(dut)
    await host.enable()

    if strict:
        # Flash: exit stale continuous mode if any.
        await host.spi_transaction(CS_FLASH, [0xFF], read_len=0)

        # Flash: enter a continuous-read-capable state.
        # This is a simulation-friendly equivalent of the RP2040/TinyQV
        # setup step. The PMOD model treats 0xEB as the quad-read setup path
        # and sets flash_continuous_mode.
        await host.spi_transaction(CS_FLASH, [0xEB, 0x00, 0x00, 0x00, 0xA0], read_len=1)

        # PSRAM: enter QPI mode on both chips.
        await host.spi_transaction(CS_RAMA, [0x35], read_len=0)
        await host.spi_transaction(CS_RAMB, [0x35], read_len=0)
    else:
        # Fast escape hatch for debugging. Tests should usually keep strict=True.
        dut.pmod.flash_continuous_mode.value = 1
        dut.pmod.ram_a_qpi_mode.value = 1
        dut.pmod.ram_b_qpi_mode.value = 1

    await host.release_to_core()
    await release_core_reset(dut)
