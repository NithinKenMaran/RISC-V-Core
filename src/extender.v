module extender(
    input [24:0] imm,
    input [1:0] imm_src,
    output reg [31:0] imm_ext
);

    always @(*) begin
        case (imm_src)
            2'b00: imm_ext = {{20{imm[24]}}, imm[24:13]}; // I-type
            2'b01: imm_ext = {{20{imm[24]}}, imm[24:18], imm[4:0]}; // S-type
            2'b10: imm_ext = {{19{imm[24]}}, imm[24], imm[0], imm[23:18], imm[4:1], 1'b0}; // B-type
            2'b11: imm_ext = {{11{imm[24]}}, imm[24], imm[12:5], imm[13], imm[23:14], 1'b0}; // J-type
            default: imm_ext = 32'b0;
        endcase
    end

endmodule