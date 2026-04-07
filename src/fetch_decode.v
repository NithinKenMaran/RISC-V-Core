module rv32_fetch(
    input clk, rst,

    output [31:0] instr,
    output reg [31:0] pc // need to change bit length
);

    // updating the instr_addr, PC is sequential. Current PC is latched.
    always @(posedge clk) begin
        if (rst)
            pc <= 32'd0;
        else
            pc <= pc + 32'd4;
    end

    // memory access is combinational,

    imem memory (
        .instr_addr(pc),
        .instr(instr)
        );

endmodule


// implements fetch and decode
// Takes in the instruction, slices it, 
// generates RF inputs, and control signals
module rv32_decoder # (
    parameter ADDR_LEN = 5
)(
    input [31:0] instr,
    input zero,

    // control signals generated,
    // main decoder
    output PCSrc,
    output ResultSrc,
    output MemWrite,
    output ALUSrc,
    output [1:0] ImmSrc,
    output RegWrite,

    // alu decoder
    output [2:0] ALUControl,

    // RF addr
    output [ADDR_LEN-1:0] rs2,
    output [ADDR_LEN-1:0] rs1,
    output [ADDR_LEN-1:0] rd
);
    // slicing instruction to get inputs
    wire op = instr[6:0];
    assign rd = instr[11:7];
    wire f3 = instr[14:12];
    assign rs1 = instr[19:15];
    assign rs2 = instr[24:20];
    wire funct7 = instr[31:25];

    //
    wire Branch;
    wire ALUOp [1:0];

    //  op, f3, funct7 are used to generate control signals
    // main decoder
    main_decoder u_main_decoder(
        .op(op),
        .Branch(Branch), .ResultSrc(ResultSrc), .MemWrite(MemWrite),
        .ALUSrc(ALUSrc), .ImmSrc(ImmSrc), .RegWrite(RegWrite), .ALUOp(ALUOp)
    );

    ALU_decoder u_ALU_decoder(
        .op_5(op[5]), .f3(f3), .funct7_5(funct7[5]), .ALUOp(ALUOp),

        .ALUControl(ALUControl)
    );
    
    assign PCSrc = zero & Branch;
    

endmodule

// [4:0] x is a packed array, while x [4:0] is an unpacked array

module main_decoder(
    input [6:0] op,
    // main decoder
    output Branch,
    output ResultSrc,
    output MemWrite,
    output ALUSrc,
    output [1:0] ImmSrc,
    output RegWrite,

    output [1:0] ALUOp
);

    //
    

endmodule

module ALU_decoder(
    input op_5,
    input [2:0] f3,
    input funct7_5,
    input [1:0] ALUOp,

    output [2:0] ALUControl

);
    assign ALUControl = 3'd0;


endmodule