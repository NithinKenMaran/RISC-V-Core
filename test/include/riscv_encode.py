# test/include/riscv_encode.py

# ── Generic builders ──────────────────────────────────────────────────────────

def encode_rtype(funct7, rs2, rs1, funct3, rd, opcode=0b0110011):
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    ) & 0xFFFFFFFF


def encode_itype(imm, rs1, funct3, rd, opcode):
    imm12 = imm & 0xFFF
    return (
        (imm12 << 20) | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    ) & 0xFFFFFFFF


def encode_stype(imm, rs2, rs1, funct3, opcode):
    imm12 = imm & 0xFFF
    imm11_5 = (imm12 >> 5) & 0x7F
    imm4_0  = imm12 & 0x1F
    return (
        (imm11_5 << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12) | (imm4_0 << 7)
        | (opcode & 0x7F)
    ) & 0xFFFFFFFF


def encode_btype(rs1, rs2, imm, funct3):
    if imm % 2 != 0:
        raise ValueError("branch immediate must be 2-byte aligned")
    imm &= 0x1FFF
    imm12   = (imm >> 12) & 0x1
    imm10_5 = (imm >> 5)  & 0x3F
    imm4_1  = (imm >> 1)  & 0xF
    imm11   = (imm >> 11) & 0x1
    return (
        (imm12 << 31) | (imm10_5 << 25) | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12)
        | (imm4_1 << 8) | (imm11 << 7) | 0b1100011
    ) & 0xFFFFFFFF


# ── R-type ────────────────────────────────────────────────────────────────────

def encode_add(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x0, rd)
def encode_sub(rd, rs1, rs2):  return encode_rtype(0x20, rs2, rs1, 0x0, rd)
def encode_sll(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x1, rd)
def encode_slt(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x2, rd)
def encode_sltu(rd, rs1, rs2): return encode_rtype(0x00, rs2, rs1, 0x3, rd)
def encode_xor(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x4, rd)
def encode_srl(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x5, rd)
def encode_sra(rd, rs1, rs2):  return encode_rtype(0x20, rs2, rs1, 0x5, rd)
def encode_or(rd, rs1, rs2):   return encode_rtype(0x00, rs2, rs1, 0x6, rd)
def encode_and(rd, rs1, rs2):  return encode_rtype(0x00, rs2, rs1, 0x7, rd)


# ── I-type ALU ────────────────────────────────────────────────────────────────

def encode_addi(rd, rs1, imm):  return encode_itype(imm, rs1, 0x0, rd, 0b0010011)
def encode_slti(rd, rs1, imm):  return encode_itype(imm, rs1, 0x2, rd, 0b0010011)
def encode_sltiu(rd, rs1, imm): return encode_itype(imm, rs1, 0x3, rd, 0b0010011)
def encode_xori(rd, rs1, imm):  return encode_itype(imm, rs1, 0x4, rd, 0b0010011)
def encode_ori(rd, rs1, imm):   return encode_itype(imm, rs1, 0x6, rd, 0b0010011)
def encode_andi(rd, rs1, imm):  return encode_itype(imm, rs1, 0x7, rd, 0b0010011)


def encode_slli(rd, rs1, shamt):
    return encode_rtype(0x00, shamt & 0x1F, rs1, 0x1, rd, opcode=0b0010011)

def encode_srli(rd, rs1, shamt):
    return encode_rtype(0x00, shamt & 0x1F, rs1, 0x5, rd, opcode=0b0010011)

def encode_srai(rd, rs1, shamt):
    return encode_rtype(0x20, shamt & 0x1F, rs1, 0x5, rd, opcode=0b0010011)


# ── U-type ────────────────────────────────────────────────────────────────────

def encode_lui(rd, imm20):
    return (((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | 0b0110111) & 0xFFFFFFFF

def encode_auipc(rd, imm20):
    return (((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | 0b0010111) & 0xFFFFFFFF


# ── Loads / stores ────────────────────────────────────────────────────────────

def encode_lw(rd, rs1, imm):
    return encode_itype(imm, rs1, 0x2, rd, 0b0000011)

def encode_sw(rs1, rs2, imm):
    # mem[rs1 + imm] = rs2
    return encode_stype(imm, rs2, rs1, 0x2, 0b0100011)


# ── Branches ─────────────────────────────────────────────────────────────────

def encode_beq(rs1, rs2, imm):  return encode_btype(rs1, rs2, imm, 0b000)
def encode_bne(rs1, rs2, imm):  return encode_btype(rs1, rs2, imm, 0b001)
def encode_blt(rs1, rs2, imm):  return encode_btype(rs1, rs2, imm, 0b100)
def encode_bge(rs1, rs2, imm):  return encode_btype(rs1, rs2, imm, 0b101)
def encode_bltu(rs1, rs2, imm): return encode_btype(rs1, rs2, imm, 0b110)
def encode_bgeu(rs1, rs2, imm): return encode_btype(rs1, rs2, imm, 0b111)


# ── Jumps ─────────────────────────────────────────────────────────────────────

def encode_jal(rd, imm):
    if imm % 2 != 0:
        raise ValueError("JAL immediate must be 2-byte aligned")
    imm &= 0x1FFFFF
    imm20    = (imm >> 20) & 0x1
    imm10_1  = (imm >> 1)  & 0x3FF
    imm11    = (imm >> 11) & 0x1
    imm19_12 = (imm >> 12) & 0xFF
    return (
        (imm20 << 31) | (imm10_1 << 21) | (imm11 << 20)
        | (imm19_12 << 12) | ((rd & 0x1F) << 7) | 0b1101111
    ) & 0xFFFFFFFF

def encode_jalr(rd, rs1, imm):
    return encode_itype(imm, rs1, 0x0, rd, 0b1100111)


# ── Misc ──────────────────────────────────────────────────────────────────────

def encode_nop():
    return 0x00000013  # addi x0, x0, 0
