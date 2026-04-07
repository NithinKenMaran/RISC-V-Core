`include "params.vh"

module riscv(
    input clk,
    input reset,
    input [`XLEN-1:0] instr
);
    wire [4:0] rs1,rs2,rd;
    wire [2:0] alu_op;

    wire [`XLEN-1:0] rdata_1, rdata_2;
    wire [`XLEN-1:0] alu_result;
    wire write_en;

    decoder dec(
        .instr(instr),
        .rs1(rs1),
        .rs2(rs2),
        .rd(rd),
        .alu_op(alu_op),
        .write_en(write_en)
    );

    registerfile rf(
        .clk(clk),
        .reset(reset),
        .rs1(rs1),
        .rs2(rs2),
        .rd_addr(rd),
        .write_en(write_en), 
        .result(alu_result),
        .rs1_data(rdata_1),
        .rs2_data(rdata_2)
    );

    alu alu_inst (
        .alu_op(alu_op),
        .a(rdata_1),
        .b(rdata_2),
        .result(alu_result)
    );

endmodule