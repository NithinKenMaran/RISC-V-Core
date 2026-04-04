`include "params.vh"

module decoder(
    input [31:0] instr,

    output reg [3:0] alu_op,

    output reg [4:0] rs2,
    output reg [4:0] rs1,
    output reg [4:0] rd,
    output [6:0] opcode,

    output is_rtype,
    output [6:0] r_funct7,
    output [2:0] r_funct3,

    output is_itype
);
    // splitting instruction
    assign opcode = instr[6:0];
    assign r_funct7 = instr[31:25];
    assign r_funct3 = instr[14:12];

    // register signals
    always @(*) begin
        if (is_rtype) begin
            rs1 = instr[19:15];
            rs2 = instr[24:20];
            rd = instr[11:7];
        end
    end

    // instruction signals
    assign is_rtype = (opcode == 7'b0110011);
    wire is_add = (r_funct3==3'b000 & r_funct7==7'b000_0000);

    // alu op
    always @(*) begin
        if (is_add) begin
            alu_op = `ALU_ADD;
        end
        else begin
            alu_op = 4'b0;
        end
    end



endmodule // decoder