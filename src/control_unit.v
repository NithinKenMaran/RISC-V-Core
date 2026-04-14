`include "params.vh"

module control_unit(
    input [6:0] op,
    input [2:0] funct3,         
    input funct7_5,
    input zero,
    input lt, 
    input ltu,
    
    output reg pc_src,
    output [1:0] result_src,
    output memwrite,
    output reg [3:0] alu_op,    
    output alu_src,
    output [1:0] imm_src,
    output reg_write
);

    // instruction type signals
    wire is_rtype, is_itype, branch;              

    assign is_rtype = (op == 7'b0110011);
    assign is_itype = (op == 7'b0010011);
    assign branch = (op == 7'b1100011);

    // branch specific 
    wire is_beq = branch && (funct3 == 3'b000); 
    wire is_bne = branch && (funct3 == 3'b001);
    wire is_blt = branch && (funct3 == 3'b100);
    wire is_bge = branch && (funct3 == 3'b101);
    wire is_bltu = branch && (funct3 == 3'b110);
    wire is_bgeu = branch && (funct3 == 3'b111);

    // CONTROL SIGNALS //

    // pc source
    always @(*) begin
        if (is_beq) begin
            pc_src = zero; // branch if equal
        end else if (is_bne) begin
            pc_src = !zero; // branch if not equal
        end else if (is_blt) begin
            pc_src = lt; // branch if less than (signed)
        end else if (is_bge) begin
            pc_src = !lt; // branch if greater than or equal (signed)
        end else if (is_bltu) begin
            pc_src = ltu; // branch if less than (unsigned)
        end else if (is_bgeu) begin
            pc_src = !ltu; // branch if greater than or equal (unsigned)
        end else begin
            pc_src = 1'b0; // next instruction
        end
    end

    assign result_src = 2'b00;
    assign memwrite  = 1'b0;
    assign imm_src   = branch ? 2'b10 : 2'b00;

    // register write enable
    assign reg_write = is_rtype || is_itype;

    // ALU source: 1 if immediate, 0 if register type
    assign alu_src = is_itype;

    always @(*) begin
        alu_op = 5'b00000;  // default

        if (is_rtype) begin
            case (funct3)
                3'b000: alu_op = funct7_5 ? `ALU_SUB  : `ALU_ADD;
                3'b001: alu_op = `ALU_SLL;
                3'b010: alu_op = `ALU_SLT;
                3'b011: alu_op = `ALU_SLTU;
                3'b100: alu_op = `ALU_XOR;
                3'b101: alu_op = funct7_5 ? `ALU_SRA  : `ALU_SRL;
                3'b110: alu_op = `ALU_OR;
                3'b111: alu_op = `ALU_AND;
                default: alu_op = 5'b00000;
            endcase
        end
        else if (is_itype) begin
            case (funct3)
                3'b000: alu_op = `ALU_ADD;                  // addi
                3'b001: alu_op = `ALU_SLL;                  // slli
                3'b010: alu_op = `ALU_SLT;                  // slti
                3'b011: alu_op = `ALU_SLTU;                 // sltiu
                3'b100: alu_op = `ALU_XOR;                  // xori
                3'b101: alu_op = funct7_5 ? `ALU_SRA
                                          : `ALU_SRL;       // srai / srli
                3'b110: alu_op = `ALU_OR;                   // ori
                3'b111: alu_op = `ALU_AND;                  // andi
                default: alu_op = 5'b00000;
            endcase
        end

        else if (branch) begin
            alu_op = `ALU_SUB; // for beq
        end
    end

endmodule // control_unit