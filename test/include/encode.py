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


# B-TYPE ENCODERS

def _encode_btype(rs1, rs2, imm, funct3):
    """
    Encode a generic B-type instruction.

    imm:
      - branch offset in bytes
      - must be 2-byte aligned
      - typically use multiples of 4 in your current setup
    """
    opcode = 0b1100011

    if imm % 2 != 0:
        raise ValueError("Branch immediate must be 2-byte aligned")

    # 13-bit signed immediate for B-type
    imm &= 0x1FFF

    imm12   = (imm >> 12) & 0x1
    imm10_5 = (imm >> 5)  & 0x3F
    imm4_1  = (imm >> 1)  & 0xF
    imm11   = (imm >> 11) & 0x1

    instr = 0
    instr |= (imm12   << 31)
    instr |= (imm10_5 << 25)
    instr |= (rs2     << 20)
    instr |= (rs1     << 15)
    instr |= (funct3  << 12)
    instr |= (imm4_1  << 8)
    instr |= (imm11   << 7)
    instr |= opcode

    return instr


def encode_beq(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b000)


def encode_bne(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b001)


def encode_blt(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b100)


def encode_bge(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b101)


def encode_bltu(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b110)


def encode_bgeu(rs1, rs2, imm):
    return _encode_btype(rs1, rs2, imm, 0b111)

# J-Type Encoders

# J-TYPE ENCODERS

def encode_jal(rd: int, imm: int) -> int:
    """
    Encode: jal rd, imm

    imm:
      - jump offset in bytes
      - must be 2-byte aligned
      - stored as J-type 21-bit signed immediate
    """
    opcode = 0b1101111

    if imm % 2 != 0:
        raise ValueError("JAL immediate must be 2-byte aligned")

    imm &= 0x1FFFFF  # 21-bit signed immediate

    imm20    = (imm >> 20) & 0x1
    imm10_1  = (imm >> 1)  & 0x3FF
    imm11    = (imm >> 11) & 0x1
    imm19_12 = (imm >> 12) & 0xFF

    instr = 0
    instr |= (imm20    << 31)
    instr |= (imm10_1  << 21)
    instr |= (imm11    << 20)
    instr |= (imm19_12 << 12)
    instr |= (rd       << 7)
    instr |= opcode

    return instr


# JALR ENCODER (jalr is I type btw)

def encode_jalr(rd: int, rs1: int, imm: int) -> int:
    """
    Encode: jalr rd, rs1, imm

    imm:
      - 12-bit signed immediate
      - I-type encoding
    """
    imm12 = imm & 0xFFF
    opcode = 0b1100111
    funct3 = 0b000

    return (
        (imm12 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )

# U type encoder 
def encode_lui(rd: int, imm20: int) -> int:
    """
    Encode: lui rd, imm20

    imm20 is the upper 20-bit immediate value, not the already-shifted 32-bit value.
    """
    imm20 &= 0xFFFFF
    opcode = 0b0110111
    return (imm20 << 12) | (rd << 7) | opcode

def encode_auipc(rd: int, imm20: int) -> int:
    """
    Encode: auipc rd, imm20

    imm20 is the upper 20-bit immediate value, not the shifted 32-bit value.
    """
    imm20 &= 0xFFFFF
    opcode = 0b0010111
    return (imm20 << 12) | (rd << 7) | opcode