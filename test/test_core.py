import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def encode_add(rd: int, rs1: int, rs2: int) -> int:
    funct7 = 0b0000000
    funct3 = 0b000
    opcode = 0b0110011
    return (
        (funct7 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )


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

    core.instr.value = encode_add(rd=3, rs1=1, rs2=2)
    core.instr_valid.value = 1
    await RisingEdge(core.clk)
    await Timer(1, units="ns")

    assert int(core.register_file.registers[3].value) == 30, (
        f"x3 wrong: got {int(core.register_file.registers[3].value)}, expected 30"
    )

    assert int(core.register_file.registers[1].value) == 10
    assert int(core.register_file.registers[2].value) == 20
