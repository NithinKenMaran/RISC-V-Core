`include "params.vh"

module core(
    input clk,
    input reset,

    input [31:0] instr_data,
    input finished
);

    // program counter
    reg [31:0] pc;
    always @(posedge clk) begin
        pc <= instr_data;
    end

    // decoder
    wire [4:0] rs1, rs2, rd;
    wire [3:0] alu_op;
    decoder decoder(
        .instr(pc),
        .rs2(rs2), 
        .rs1(rs1), 
        .rd(rd),
        .alu_op(alu_op), 
        .opcode(),
        .is_rtype(), 
        .r_funct7(), 
        .r_funct3(),
        .is_itype()
    );

    // register file

    reg w_en;
    reg [31:0] reg_w_data;

    wire [31:0] rdata_1, rdata_2;
    register_file register_file(
        .clk(clk),
        .reset(reset),

        .rs1(rs1),
        .rs2(rs2),
        .rd(rd),

        .w_en(w_en),
        .w_data(reg_w_data),
        .rdata_1(rdata_1), .rdata_2(rdata_2)
    );

    always @(*) begin
        w_en = (state == `WRITEBACK);
    end

    // alu
    wire [31:0] alu_result;
    alu alu(
        alu_op, rs1, rs2, alu_result
    );

    // state machine

    reg [2:0] state;
    wire [2:0] next_state;
    
    // next state logic
    always @(*) begin
        case (state) 
            `FETCH: next_state = `EXECUTE;
            `EXECUTE: next_state = `WRITEBACK;
            `WRITEBACK: next_state = finished ? `FINISH : `FETCH;
        endcase
    end

    // state machine
    always @(posedge clk) begin
        state <= next_state
    end

endmodule; // core