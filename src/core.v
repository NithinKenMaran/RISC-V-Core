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
    reg [31:0] pc_next;
    always @(posedge clk) begin
        if (reset) begin
            pc <= 32'b0;
        end else if (instr_valid) begin
            pc <= pc_next;
        end 
    end

    wire [31:0] pc_plus_4;
    assign pc_plus_4 = pc + 4;

    always @(*) begin
        case (pc_src)
            2'b00: pc_next = pc_plus_4;
            2'b01: pc_next = pc + imm_ext;
            2'b10: pc_next = alu_result & 32'hFFFFFFFE; // for jalr, last bit has to be set to zero.
            default: pc_next = pc_plus_4;
        endcase
    end

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
    wire [1:0] pc_src;
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
        .lt(lt), 
        .ltu(ltu),

        .pc_src(pc_src),
        .result_src(result_src),
        .memwrite(memwrite),
        .alu_op(alu_op),
        .alu_src(alu_src),
        .imm_src(imm_src),
        .reg_write(reg_write)
    );

    // register file
    reg [31:0] reg_w_data;

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

    always @(*) begin
        case (result_src)
            2'b00: reg_w_data = alu_result; // ALU result
            2'b10: reg_w_data = pc + 4; // for jal & jalr
            2'b01: reg_w_data = 32'b0; // for load (not implemented yet)
            default: reg_w_data = 32'b0;
        endcase
    end

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
    wire zero, lt, ltu;
    // lt: less than?
    // ltu: less than (unsigned)?

    assign src_a = rdata_1;
    assign src_b = alu_src ? imm_ext : rdata_2;

    alu alu(
        .alu_op(alu_op),
        .a(src_a),
        .b(src_b),
        .result(alu_result),
        .zero(zero),
        .lt(lt),
        .ltu(ltu)
    );

endmodule; // core
