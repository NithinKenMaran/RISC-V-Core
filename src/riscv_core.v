module rv32_core #(
    parameter WORD_LEN = 32,
    parameter ADDR_LEN = 5
)(
    input clk, rst
);
    wire [N-1:0] pc;
    wire [31:0] instr;
    wire zero; // zero flag
    // main decoder
    wire PCSrc;
    wire ResultSrc;
    wire MemWrite;
    wire ALUSrc;
    wire [1:0] ImmSrc;
    wire RegWrite;
    // alu decoder
    wire [2:0] ALUControl;
    // RF addr
    wire [ADDR_LEN-1:0] rs2;
    wire [ADDR_LEN-1:0] rs1;
    wire [ADDR_LEN-1:0] rd;
    input [WORD_LEN-1:0] WD; // write data
    // read data
    wire [WORD_LEN-1:0] RD1;
    wire [WORD_LEN-1:0] RD2;
    // mid RF ALU circuitry
    wire [WORD_LEN-1:0] SrcA;
    wire [WORD_LEN-1:0] SrcB;
    wire [WORD_LEN-1:0] ALUResult;

    // fetch, has the program counter
    rv32_fetch u_fetch (
        .clk(clk), .rst(rst),
        .instr(instr), .pc(pc)
    );

    // decode
    rv32_decoder u_decode (
        .instr(instr), .zero(zero), 
        .PCSrc(PCSrc),
        .ResultSrc(ResultSrc),
        .MemWrite(MemWrite),
        .ALUSrc(ALUSrc),
        .ImmSrc(ImmSrc),
        .RegWrite(RegWrite),
        .ALUControl(ALUControl),
        .rs2(rs2),
        .rs1(rs1),
        .rd(rd)
    );

    rv32_regfile u_regfile (
        .clk(clk),
        .WE(RegWrite),
        .A1(rs1),
        .A2(rs2),
        .A3(rs3),
        .WD(WD),
        .RD1(RD1),
        .RD2(RD2)
    );

    assign SrcA = RD1;
    assign SrcB = RD2;

    rv32_alu u_alu (
        .SrcA(SrcA), .SrcB(SrcB),
        .ALUControl(ALUControl),
        .zero(zero), .ALUResult(ALUResult)
    );

    assign WD = ALUResult;

endmodule