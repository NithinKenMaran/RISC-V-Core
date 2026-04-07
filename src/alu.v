module rv32_alu # (parameter WORD_LEN = 32)(
    input [WORD_LEN-1:0] SrcA,
    input [WORD_LEN-1:0] SrcB,
    input [2:0] ALUControl,

    output zero,
    output reg [WORD_LEN-1:0] ALUResult
    // note: reg doesn't mean it get's synthesized to reg
    // wire, reg are just variables and,
    // do not truly indicate what they are synthesized into
);

    always @(*) begin

        case(ALUControl)
            3'b000: ALUResult = SrcA + SrcB;
            3'b001: ALUResult = SrcA - SrcB;
            3'b010: ALUResult = SrcA & SrcB;
            3'b011: ALUResult = SrcA | SrcB;
            3'b101: ALUResult = SrcA < SrcB;
        endcase
    end
    

endmodule