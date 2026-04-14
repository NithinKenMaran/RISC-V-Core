`include "params.vh"
// `define DEBUG

module core(
    input clk,
    input reset,

    input wire [31:0] instr,

    // instr_valid is unused for now
    // right now, test_core.py appropriately asserts instruction
    // then waits for 1 ns and reads outputs.
    input instr_valid,

    output reg [31:0] pc
    );


    // program counter logic
    wire [31:0] pc_next;
    always @(posedge clk) begin
        if (reset) begin
            pc <= 32'b0;
        end else if (instr_valid) begin
            pc <= pc_next;
        end else begin
            pc <= pc; // hold the value
        end
    end

    assign pc_next = pc_src ? pc + imm_ext : pc + 4;

    

    // decoder
    wire [6:0] op;
    wire [2:0] funct3;
    wire funct7_5;
    wire [4:0] rs1, rs2, rd;
    wire [24:0] imm;

    decoder decoder (
        .instr(instr),

        .op(op),
        .funct3(funct3),
        .funct7_5(funct7_5),

        .rs1(rs1),
        .rs2(rs2),
        .rd(rd),

        .imm(imm)        
    );

    // control unit
    wire pc_src;
    wire [1:0] result_src;
    wire memwrite;
    wire [3:0] alu_op;
    wire alu_src;
    wire [1:0] imm_src;
    wire reg_write;

    control_unit control_unit (
        .op(op),
        .funct3(funct3),
        .funct7_5(funct7_5),
        .zero(zero),

        .pc_src(pc_src),
        .result_src(result_src),
        .memwrite(memwrite),
        .alu_op(alu_op),
        .alu_src(alu_src),
        .imm_src(imm_src),
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

    // extender
    wire [31:0] imm_ext;
    extender extender (
        .imm(imm),
        .imm_src(imm_src),
        .imm_ext(imm_ext) 
    );

    // alu
    wire [31:0] alu_result;
    wire [31:0] src_a, src_b;
    wire zero;

    assign src_a = rdata_1;
    assign src_b = alu_src ? imm_ext : rdata_2;

    alu alu(
        .alu_op(alu_op),
        .a(src_a),
        .b(src_b),
        .result(alu_result),
        .zero(zero)
    );

endmodule; // core
