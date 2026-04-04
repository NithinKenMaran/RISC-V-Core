module register_file(
    input clk,
    input reset,
    
    input [4:0] rs1,
    input [4:0] rs2, 
    input [4:0] rd,

    input w_en,
    input [31:0] w_data,

    output reg [31:0] rdata_1,
    output reg [31:0] rdata_2
);

    wire [31:0] x0 = {32{1'b0}};
    
    reg [31:0] registers [1: 31];


    // reading
    always @(*) begin
        rdata_1 = registers[rs1];
        rdata_2 = registers[rs2];
    end

    // writing
    always @(posedge clk) begin
        if (w_en) begin
            registers[rd] <= w_data;
        end
    end

endmodule; // register_file