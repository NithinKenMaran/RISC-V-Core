`include "params.vh"

module control_unit(
    input  wire [6:0] op,
    input  wire [2:0] funct3,
    input  wire       funct7_5,

    input  wire       zero,
    input  wire       lt,
    input  wire       ltu,

    // Trap decode from decoder (full-word comparisons)
    input  wire       is_ecall,
    input  wire       is_ebreak,

    output reg  [1:0] pc_src,
    output reg  [2:0] result_src,

    output wire       mem_read,
    output wire       mem_write,

    output reg  [3:0] alu_op,
    output wire       alu_src,

    output reg  [2:0] imm_src,
    output wire       reg_write,

    // extra decoded signals used by the externalized-state FSM
    output wire       uses_rs1,
    output wire       uses_rs2,
    output wire       is_load,
    output wire       is_store,
    output wire       is_branch,
    output wire       is_jal,
    output wire       is_jalr,
    output wire       is_trap_instr
);

    // ----------------------------
    // Opcode decode
    // ----------------------------

    wire is_rtype;
    wire is_itype;
    wire is_lui;
    wire is_auipc;

    assign is_trap_instr = is_ecall | is_ebreak;

    assign is_rtype  = (op == 7'b0110011);
    assign is_itype  = (op == 7'b0010011);
    assign is_load   = (op == 7'b0000011);
    assign is_store  = (op == 7'b0100011);
    assign is_branch = (op == 7'b1100011);
    assign is_jal    = (op == 7'b1101111);
    assign is_jalr   = (op == 7'b1100111) && (funct3 == 3'b000);
    assign is_lui    = (op == 7'b0110111);
    assign is_auipc  = (op == 7'b0010111);

    wire is_lw;
    wire is_sw;

    assign is_lw = is_load  && (funct3 == 3'b010);
    assign is_sw = is_store && (funct3 == 3'b010);

    // ----------------------------
    // Which source registers are actually needed?
    // ----------------------------

    assign uses_rs1 =
        is_rtype  ||
        is_itype  ||
        is_load   ||
        is_store  ||
        is_branch ||
        is_jalr;

    assign uses_rs2 =
        is_rtype  ||
        is_store  ||
        is_branch;

    // ----------------------------
    // Branch decode
    // ----------------------------

    wire is_beq;
    wire is_bne;
    wire is_blt;
    wire is_bge;
    wire is_bltu;
    wire is_bgeu;

    assign is_beq  = is_branch && (funct3 == 3'b000);
    assign is_bne  = is_branch && (funct3 == 3'b001);
    assign is_blt  = is_branch && (funct3 == 3'b100);
    assign is_bge  = is_branch && (funct3 == 3'b101);
    assign is_bltu = is_branch && (funct3 == 3'b110);
    assign is_bgeu = is_branch && (funct3 == 3'b111);

    wire branch_taken;

    assign branch_taken =
        (is_beq  &&  zero) ||
        (is_bne  && !zero) ||
        (is_blt  &&  lt)   ||
        (is_bge  && !lt)   ||
        (is_bltu &&  ltu)  ||
        (is_bgeu && !ltu);

    // ----------------------------
    // PC source
    //
    // 00 = pc + 4
    // 01 = pc + imm
    // 10 = rs1 + imm, for jalr
    // ----------------------------

    always @(*) begin
        if (is_jalr) begin
            pc_src = 2'b10;
        end else if (is_jal || branch_taken) begin
            pc_src = 2'b01;
        end else begin
            pc_src = 2'b00;
        end
    end

    // ----------------------------
    // Result source
    //
    // 000 = ALU result
    // 001 = memory read data
    // 010 = pc + 4
    // 011 = immediate, for LUI
    // 100 = pc + imm, for AUIPC
    // ----------------------------

    always @(*) begin
        if (is_lw) begin
            result_src = 3'b001;
        end else if (is_jal || is_jalr) begin
            result_src = 3'b010;
        end else if (is_lui) begin
            result_src = 3'b011;
        end else if (is_auipc) begin
            result_src = 3'b100;
        end else begin
            result_src = 3'b000;
        end
    end

    // ----------------------------
    // Memory controls
    // ----------------------------

    assign mem_read  = is_lw;
    assign mem_write = is_sw;

    // ----------------------------
    // Immediate source
    //
    // 000 = I-type
    // 001 = S-type
    // 010 = B-type
    // 011 = U-type
    // 100 = J-type
    // ----------------------------

    always @(*) begin
        if (is_store) begin
            imm_src = 3'b001;
        end else if (is_branch) begin
            imm_src = 3'b010;
        end else if (is_lui || is_auipc) begin
            imm_src = 3'b011;
        end else if (is_jal) begin
            imm_src = 3'b100;
        end else begin
            imm_src = 3'b000;
        end
    end

    // ----------------------------
    // Register write enable
    // ----------------------------

    assign reg_write =
        is_rtype ||
        is_itype ||
        is_lw    ||
        is_jal   ||
        is_jalr  ||
        is_lui   ||
        is_auipc;

    // ----------------------------
    // ALU source
    //
    // 0 = rs2
    // 1 = immediate
    // ----------------------------

    assign alu_src =
        is_itype ||
        is_load  ||
        is_store ||
        is_jalr;

    // ----------------------------
    // ALU operation
    // ----------------------------

    always @(*) begin
        alu_op = `ALU_ADD;

        if (is_rtype) begin
            case (funct3)
                3'b000: alu_op = funct7_5 ? `ALU_SUB : `ALU_ADD;
                3'b001: alu_op = `ALU_SLL;
                3'b010: alu_op = `ALU_SLT;
                3'b011: alu_op = `ALU_SLTU;
                3'b100: alu_op = `ALU_XOR;
                3'b101: alu_op = funct7_5 ? `ALU_SRA : `ALU_SRL;
                3'b110: alu_op = `ALU_OR;
                3'b111: alu_op = `ALU_AND;
                default: alu_op = `ALU_ADD;
            endcase
        end else if (is_itype) begin
            case (funct3)
                3'b000: alu_op = `ALU_ADD;              // addi
                3'b001: alu_op = `ALU_SLL;              // slli
                3'b010: alu_op = `ALU_SLT;              // slti
                3'b011: alu_op = `ALU_SLTU;             // sltiu
                3'b100: alu_op = `ALU_XOR;              // xori
                3'b101: alu_op = funct7_5 ? `ALU_SRA
                                          : `ALU_SRL;   // srai / srli
                3'b110: alu_op = `ALU_OR;               // ori
                3'b111: alu_op = `ALU_AND;              // andi
                default: alu_op = `ALU_ADD;
            endcase
        end else if (is_branch) begin
            alu_op = `ALU_SUB;
        end else if (is_load || is_store || is_jalr || is_auipc) begin
            alu_op = `ALU_ADD;
        end else begin
            alu_op = `ALU_ADD;
        end
    end

endmodule