`include "params.vh"

module registerfile(
    input clk,
    input reset,
    input [4:0] rs1, rs2, rd_addr,
    input write_en,
    input [`XLEN-1:0]result,
    output [`XLEN-1:0] rs1_data,rs2_data
);
    reg [`XLEN-1:0] registers [0:`REG_COUNT-1];
    integer i;

    assign rs1_data = registers[rs1];
    assign rs2_data = registers[rs2];

    initial begin
        registers[0] = {`XLEN{1'b0}};
    end

    always @(posedge clk) begin
        if(reset) begin
            for(i=0;i<`REG_COUNT;i=i+1)
                registers[i] <= 0;
        end
        else if(write_en && rd_addr!=0) begin
            registers[rd_addr] <= result;
        end

    end

endmodule