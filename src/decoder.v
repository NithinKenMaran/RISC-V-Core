`include "params.vh"

module decoder(
    input [31:0] instr,

    output reg [4:0] rs2,
    output reg [4:0] rs1,
    output reg [4:0] rd,

    output reg [3:0] alu_op,
    output [6:0] opcode,

    output is_rtype,
    output is_add,
    output [6:0] r_funct7,
    output [2:0] r_funct3,

    output reg_write,

    output is_itype
);
    // splitting instruction
    assign opcode = instr[6:0];
    assign r_funct7 = instr[31:25];
    assign r_funct3 = instr[14:12];

    // register signals
    always @(*) begin
        rs1 = 5'b0;
        rs2 = 5'b0;
        rd = 5'b0;

        if (is_rtype) begin
            rs1 = instr[19:15];
            rs2 = instr[24:20];
            rd = instr[11:7];
        end
    end

    // instruction signals
    assign is_rtype = (opcode == 7'b0110011);
    assign is_itype = (opcode == 7'b0010011);
    assign is_add  = is_rtype && (r_funct3 == 3'b000) && (r_funct7 == 7'b0000000);
    wire is_sub    = is_rtype && (r_funct3 == 3'b000) && (r_funct7 == 7'b0100000);
    wire is_sll    = is_rtype && (r_funct3 == 3'b001) && (r_funct7 == 7'b0000000);
    wire is_slt    = is_rtype && (r_funct3 == 3'b010) && (r_funct7 == 7'b0000000);
    wire is_sltu   = is_rtype && (r_funct3 == 3'b011) && (r_funct7 == 7'b0000000);
    wire is_xor    = is_rtype && (r_funct3 == 3'b100) && (r_funct7 == 7'b0000000);
    wire is_srl    = is_rtype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0000000);
    wire is_sra    = is_rtype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0100000);
    wire is_or     = is_rtype && (r_funct3 == 3'b110) && (r_funct7 == 7'b0000000);
    wire is_and    = is_rtype && (r_funct3 == 3'b111) && (r_funct7 == 7'b0000000);

    // alu op
    always @(*) begin
        if (is_add)       alu_op = `ALU_ADD;
        else if (is_sub)  alu_op = `ALU_SUB;
        else if (is_sll)  alu_op = `ALU_SLL;
        else if (is_slt)  alu_op = `ALU_SLT;
        else if (is_sltu) alu_op = `ALU_SLTU;
        else if (is_xor)  alu_op = `ALU_XOR;
        else if (is_srl)  alu_op = `ALU_SRL;
        else if (is_sra)  alu_op = `ALU_SRA;
        else if (is_or)   alu_op = `ALU_OR;
        else if (is_and)  alu_op = `ALU_AND;
        else              alu_op = 4'b0;
    end


    // LOOK HERE
    // CHANGE THIS WHEN IMPLEMENTING NON-RTYPE INSTR
    assign reg_write = is_rtype;


endmodule // decoder
