`include "params.vh"

module decoder(
    input [`XLEN-1:0] instr,
    output reg [4:0] rs1,
    output reg [4:0] rs2,
    output reg [4:0] rd,
    output reg [2:0] alu_op,
    output reg write_en
);
wire [6:0] opcode = instr[6:0];

always @(*) begin
    rs1 = 0;
    rs2 = 0;
    rd = 0;
    alu_op = 0;
    write_en = 0;

    case(opcode)
        `RType : begin
            rs1 = instr [19:15];
            rs2 = instr [24:20];
            rd  = instr [11:7];

            //{func7, func3} -> {7'b0,3'b0}
            case ({instr[31:25], instr[14:12]})
                {7'b0,3'b0} : begin
                    alu_op = `ALU_ADD;
                    write_en = 1;
                end
                default : begin
                    alu_op = 0;
                    write_en = 0;
                end
            endcase
        end
    endcase
end

endmodule