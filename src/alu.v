`include "params.vh"

module alu(
    input [3:0] alu_op,

    input [31:0] a,
    input [31:0] b,
    output reg [31:0] result,
    output zero,
    output lt, 
    output ltu
);
    always @(*) begin
        case (alu_op)
            `ALU_ADD:  result = a + b;
            `ALU_SUB:  result = a - b;
            `ALU_SLL:  result = a << b[4:0];
            `ALU_SLT:  result = ($signed(a) < $signed(b)) ? 32'd1 : 32'd0;
            `ALU_SLTU: result = (a < b) ? 32'd1 : 32'd0;
            `ALU_XOR:  result = a ^ b;
            `ALU_SRL:  result = a >> b[4:0];
            `ALU_SRA:  result = $signed(a) >>> b[4:0];
            `ALU_OR:   result = a | b;
            `ALU_AND:  result = a & b;
            default:   result = 32'b0;
        endcase
    end

    assign zero = (result == 32'b0);
    assign lt = ($signed(a) < $signed(b));
    assign ltu = (a < b);

endmodule // alu
