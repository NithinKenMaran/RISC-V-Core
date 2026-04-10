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

    `ifdef DEBUG
        ,output wire [31:0] x1_db
        ,output wire [31:0] x2_db
        ,output wire [31:0] x3_db
    `endif
);

    integer i;
    reg [31:0] registers [0:31];

    `ifdef DEBUG
        assign x1_db = registers[1];
        assign x2_db = registers[2];
        assign x3_db = registers[3];
    `endif


    // reading
    always @(*) begin
        rdata_1 = (rs1 == 5'b0) ? 32'b0 : registers[rs1];
        rdata_2 = (rs2 == 5'b0) ? 32'b0 : registers[rs2];
    end

    // writing
    always @(posedge clk) begin
        if (reset) begin
            for (i = 0; i < 32; i = i + 1) begin
                registers[i] <= 32'b0;
            end
        end
        else if (w_en && rd != 5'b0) begin
            registers[rd] <= w_data;
        end
        registers[0] <= 32'b0; //r0 = 0
    end

endmodule; // register_file
