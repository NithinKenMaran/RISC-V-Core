# test/include/qspi_host.py
#
# Low-level RP2040-like QSPI host helpers for Phase A.
# These drive the simulation-only host_* pins exposed by top_qspi_tb.v.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge


CS_FLASH = 0
CS_RAMA  = 1
CS_RAMB  = 2


async def start_system_clock(dut, period_ns=10):
    """Start the core clock."""
    cocotb.start_soon(Clock(dut.clk, period_ns, units="ns").start())
    await Timer(1, units="ns")


async def wait_core_cycles(dut, cycles):
    for _ in range(cycles):
        await RisingEdge(dut.clk)


class QspiHost:
    def __init__(self, dut, half_period_ns=5):
        self.dut = dut
        self.half_period_ns = half_period_ns

    async def _delay(self):
        await Timer(self.half_period_ns, units="ns")

    async def enable(self):
        self.dut.host_active.value = 1
        self.dut.host_sck.value = 0
        self.dut.host_cs_n.value = 0b111
        self.dut.host_dq_oe.value = 0
        self.dut.host_dq_out.value = 0
        await self._delay()

    async def release_to_core(self):
        self.dut.host_sck.value = 0
        self.dut.host_cs_n.value = 0b111
        self.dut.host_dq_oe.value = 0
        self.dut.host_dq_out.value = 0
        await self._delay()
        self.dut.host_active.value = 0
        await self._delay()

    async def _cs_low(self, cs_index):
        self.dut.host_cs_n.value = 0b111 & ~(1 << cs_index)
        await self._delay()

    async def _cs_high(self):
        self.dut.host_sck.value = 0
        self.dut.host_cs_n.value = 0b111
        self.dut.host_dq_oe.value = 0
        await self._delay()

    async def _tick(self):
        self.dut.host_sck.value = 0
        await self._delay()
        self.dut.host_sck.value = 1
        await self._delay()

    async def spi_write_byte(self, byte):
        """Write one byte in single-SPI mode on IO0/MOSI, MSB first."""
        self.dut.host_dq_oe.value = 1
        for bit in range(7, -1, -1):
            v = (byte >> bit) & 1
            self.dut.host_dq_out.value = v  # IO0 only; other bits low
            await self._tick()

    async def spi_read_byte(self):
        """Read one byte from IO1/MISO, MSB first."""
        self.dut.host_dq_oe.value = 0
        value = 0
        for _ in range(8):
            self.dut.host_sck.value = 0
            await self._delay()
            self.dut.host_sck.value = 1
            await self._delay()
            # Only IO1/MISO (bit 1) is driven in SPI mode; other bits float as z.
            # binstr is MSB-first so bit 1 of a 4-bit signal is at index [-2].
            miso = 1 if self.dut.host_dq_in.value.binstr[-2] == '1' else 0
            value = (value << 1) | miso
        return value

    async def spi_transaction(self, cs_index, tx_bytes, read_len=0):
        await self._cs_low(cs_index)
        for b in tx_bytes:
            await self.spi_write_byte(int(b) & 0xFF)
        rx = []
        for _ in range(read_len):
            rx.append(await self.spi_read_byte())
        await self._cs_high()
        return bytes(rx)

    async def qpi_write_nibble(self, nibble):
        self.dut.host_dq_oe.value = 1
        self.dut.host_dq_out.value = int(nibble) & 0xF
        await self._tick()

    async def qpi_write_byte(self, byte):
        await self.qpi_write_nibble((byte >> 4) & 0xF)
        await self.qpi_write_nibble(byte & 0xF)

    async def qpi_read_byte(self):
        self.dut.host_dq_oe.value = 0
        value = 0
        for _ in range(2):
            self.dut.host_sck.value = 0
            await self._delay()
            self.dut.host_sck.value = 1
            await self._delay()
            value = (value << 4) | (int(self.dut.host_dq_in.value) & 0xF)
        return value

    async def qpi_transaction(self, cs_index, tx_bytes, dummy_nibbles=0, read_len=0):
        await self._cs_low(cs_index)
        for b in tx_bytes:
            await self.qpi_write_byte(int(b) & 0xFF)
        self.dut.host_dq_oe.value = 0
        for _ in range(dummy_nibbles):
            await self._tick()
        rx = []
        for _ in range(read_len):
            rx.append(await self.qpi_read_byte())
        await self._cs_high()
        return bytes(rx)
