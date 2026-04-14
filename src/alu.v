`include "params.vh"
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
            `ALU_ADD: ALUResult = SrcA + SrcB;
            `ALU_SUB: ALUResult = SrcA - SrcB;
            `ALU_AND: ALUResult = SrcA & SrcB;
            `ALU_OR: ALUResult = SrcA | SrcB;
            `ALU_SLT: ALUResult = SrcA < SrcB;
        endcase
    end

    assign zero = (ALUResult == 32'b0);
    

endmodule