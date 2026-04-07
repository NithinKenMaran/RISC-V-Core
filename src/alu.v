`include "params.vh"

module alu(
    input [`XLEN-1:0] a,
    input [`XLEN-1:0] b,
    input [2:0] alu_op,  
    output reg [`XLEN-1:0] result
);

always @(*) begin
    case (alu_op)
        `ALU_ADD : result = a + b;
        default: result = 0;
    endcase
end

endmodule