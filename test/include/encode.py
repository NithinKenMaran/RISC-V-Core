### R Type encoders

def encode_add(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b000 << 12) | (rd << 7) | 0b0110011)

def encode_sub(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0100000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b000 << 12) | (rd << 7) | 0b0110011)

def encode_sll(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b001 << 12) | (rd << 7) | 0b0110011)

def encode_slt(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b010 << 12) | (rd << 7) | 0b0110011)

def encode_sltu(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b011 << 12) | (rd << 7) | 0b0110011)

def encode_xor(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b100 << 12) | (rd << 7) | 0b0110011)

def encode_srl(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b101 << 12) | (rd << 7) | 0b0110011)

def encode_sra(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0100000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b101 << 12) | (rd << 7) | 0b0110011)

def encode_or(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b110 << 12) | (rd << 7) | 0b0110011)

def encode_and(rd: int, rs1: int, rs2: int) -> int:
    return ((0b0000000 << 25) | (rs2 << 20) | (rs1 << 15) |
            (0b111 << 12) | (rd << 7) | 0b0110011)

### I Type encoders

def encode_itype_alu(rd: int, rs1: int, imm: int, funct3: int) -> int:
    imm12 = imm & 0xFFF
    return (
        (imm12 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | 0b0010011
    )


def encode_addi(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b000)


def encode_slti(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b010)


def encode_sltiu(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b011)


def encode_xori(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b100)


def encode_ori(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b110)


def encode_andi(rd: int, rs1: int, imm: int) -> int:
    return encode_itype_alu(rd, rs1, imm, 0b111)


def encode_slli(rd: int, rs1: int, shamt: int) -> int:
    shamt &= 0x1F
    return (
        (0b0000000 << 25)
        | (shamt << 20)
        | (rs1 << 15)
        | (0b001 << 12)
        | (rd << 7)
        | 0b0010011
    )


def encode_srli(rd: int, rs1: int, shamt: int) -> int:
    shamt &= 0x1F
    return (
        (0b0000000 << 25)
        | (shamt << 20)
        | (rs1 << 15)
        | (0b101 << 12)
        | (rd << 7)
        | 0b0010011
    )


def encode_srai(rd: int, rs1: int, shamt: int) -> int:
    shamt &= 0x1F
    return (
        (0b0100000 << 25)
        | (shamt << 20)
        | (rs1 << 15)
        | (0b101 << 12)
        | (rd << 7)
        | 0b0010011
    )

