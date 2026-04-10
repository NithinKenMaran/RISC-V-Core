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
