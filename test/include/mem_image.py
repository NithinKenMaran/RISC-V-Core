# test/include/mem_image.py
#
# Memory image helpers. The current qspi_ctrl.v assembles read data MS-nibble
# first into a 32-bit word. Therefore, for this RTL revision, 32-bit words in
# the external byte-addressed memories are stored big-endian:
#
#   word 0x002081B3 at address 0 -> 00 20 81 B3
#
# This is a property of the current qspi_ctrl.v assembly logic, not a statement
# about how RISC-V binaries are normally laid out in byte-addressed memory.

from pathlib import Path


class MemoryImage:
    def __init__(self, size=1 << 16, fill=0x00):
        self.size = size
        self.data = bytearray([fill & 0xFF] * size)
        self.touched = set()

    def set_byte(self, addr, value):
        addr = int(addr)
        if not (0 <= addr < self.size):
            raise ValueError(f"address 0x{addr:x} outside image size {self.size}")
        self.data[addr] = int(value) & 0xFF
        self.touched.add(addr)

    def set_word_qspi(self, addr, value):
        """Store word in the byte order expected by the current qspi_ctrl.v."""
        value = int(value) & 0xFFFFFFFF
        self.set_byte(addr + 0, (value >> 24) & 0xFF)
        self.set_byte(addr + 1, (value >> 16) & 0xFF)
        self.set_byte(addr + 2, (value >> 8) & 0xFF)
        self.set_byte(addr + 3, value & 0xFF)

    def get_word_qspi(self, addr):
        return (
            (self.data[addr + 0] << 24)
            | (self.data[addr + 1] << 16)
            | (self.data[addr + 2] << 8)
            | self.data[addr + 3]
        ) & 0xFFFFFFFF

    def write_hex(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            for b in self.data:
                f.write(f"{b:02x}\n")


def reg_addr(reg_index):
    return int(reg_index) * 4


def write_word_to_pmod_array(array_handle, addr, value):
    value = int(value) & 0xFFFFFFFF
    array_handle[addr + 0].value = (value >> 24) & 0xFF
    array_handle[addr + 1].value = (value >> 16) & 0xFF
    array_handle[addr + 2].value = (value >> 8) & 0xFF
    array_handle[addr + 3].value = value & 0xFF


def read_word_from_pmod_array(array_handle, addr):
    return (
        (int(array_handle[addr + 0].value) << 24)
        | (int(array_handle[addr + 1].value) << 16)
        | (int(array_handle[addr + 2].value) << 8)
        | int(array_handle[addr + 3].value)
    ) & 0xFFFFFFFF


async def load_images_into_pmod(dut, flash_img, rama_img, ramb_img):
    """
    Load the same images written to test/mem/*.hex into the behavioral PMOD.

    Why this exists:
      cocotb test code runs after Verilog initial blocks. If a test creates
      test/mem/*.hex inside the test coroutine, qspi_pmod's initial $readmemh
      has already happened. This helper keeps the generated files as the
      source of truth, then mirrors them into the PMOD arrays.
    """
    for addr in sorted(flash_img.touched):
        dut.pmod.flash[addr].value = flash_img.data[addr]
    for addr in sorted(rama_img.touched):
        dut.pmod.ram_a[addr].value = rama_img.data[addr]
    for addr in sorted(ramb_img.touched):
        dut.pmod.ram_b[addr].value = ramb_img.data[addr]
