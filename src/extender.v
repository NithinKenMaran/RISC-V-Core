module rv32_extend(
    input [11:0] imm,
    input [1:0] ImmSrc,
    
    output reg [31:0] ImmExt

);

    always@(*) begin
        case(ImmSrc)
            2'b00: ImmExt = {{20{imm[11]}}, imm};
            2'b01: ImmExt = {{20{imm[11]}}, imm};
            2'b10: ImmExt = {{19{imm[11]}}, imm, 1'b0};
        endcase
    end


endmodule