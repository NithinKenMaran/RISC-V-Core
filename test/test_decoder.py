import cocotb 
from cocotb.triggers import Timer

@cocotb.test()
async def test_rtype(decoder):
    decoder.instr.value = 0x003100b3
    await Timer(3, units="ns")
    assert int(decoder.is_rtype.value)==1

@cocotb.test()
async def test_aluop(decoder):
    decoder.instr.value = 0x003100b3
    await Timer(1, units="ns")
    assert int(decoder.alu_op.value)==0

@cocotb.test()
async def test_add1(decoder):
    decoder.instr.value = 0x003100b3
    await Timer(1, units="ns")
    assert int(decoder.is_add.value)==1
