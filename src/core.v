`include "params.vh"

module core(
    input clk,
    input reset,

    input wire [31:0] instr,

    input instr_valid
);


    // decoder
    wire [4:0] rs1, rs2, rd;
    wire [3:0] alu_op;
    wire is_add;
    wire reg_write;

    decoder decoder(
        .instr(instr),
        .rs2(rs2), 
        .rs1(rs1), 
        .rd(rd),
        .alu_op(alu_op), 
        .opcode(),
        .is_rtype(), 
        .is_add(is_add),
        .r_funct7(), 
        .r_funct3(),
        .is_itype(),
        .reg_write(reg_write)

    );

    // register file

    wire [31:0] reg_w_data;

    `ifdef DEBUG
        wire [31:0] x1_db, x2_db, x3_db;
    `endif

    wire [31:0] rdata_1, rdata_2;
    register_file register_file(
        .clk(clk),
        .reset(reset),

        .rs1(rs1),
        .rs2(rs2),
        .rd(rd),

        .w_en(reg_write),
        .w_data(reg_w_data),
        .rdata_1(rdata_1), 
        .rdata_2(rdata_2)

        `ifdef DEBUG
            ,.x1_db(x1_db)
            ,.x2_db(x2_db)
            ,.x3_db(x3_db)
        `endif
    );

    assign reg_w_data = alu_result;

    // alu
    wire [31:0] alu_result;
    alu alu(
        .alu_op(alu_op),
        .a(rdata_1),
        .b(rdata_2),
        .result(alu_result)
    );

endmodule; // core
