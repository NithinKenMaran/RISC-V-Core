`include "params.vh"

module decoder(
    input [31:0] instr,

    output [6:0] op,
    output [2:0] funct3,
    output funct7_5,

    output [4:0] rs1,
    output [4:0] rs2,
    output [4:0] rd,

    output [24:0] imm,

    output is_ecall,
    output is_ebreak
);
    assign op = instr[6:0];
    assign funct3 = instr[14:12];
    assign funct7_5 = instr[30];

    assign rs1 = instr[19:15];
    assign rs2 = instr[24:20];
    assign rd  = instr[11:7];

    assign imm = instr[31:7];

    assign is_ecall  = (instr == 32'h00000073);
    assign is_ebreak = (instr == 32'h00100073);

endmodule // decoder