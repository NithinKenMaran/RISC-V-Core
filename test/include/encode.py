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