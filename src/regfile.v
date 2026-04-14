module rv32_regfile #(
    parameter WORD_LEN = 32,
    parameter REG_COUNT = 32,
    parameter ADDR_LEN = 5
)(
    input clk,

    input WE, // write enable
    // regfile addr
    input [ADDR_LEN-1:0] A1,
    input [ADDR_LEN-1:0] A2,
    input [ADDR_LEN-1:0] A3, // write addr

    input [WORD_LEN-1:0] WD, // write data

    // read data
    output [WORD_LEN-1:0] RD1,
    output [WORD_LEN-1:0] RD2
);

    reg [WORD_LEN-1:0] regfile [0:REG_COUNT-1];

    // read is combinational
    assign RD1 = (A1!=0)? regfile[A1] : 0;
    assign RD2 = (A2!=0)? regfile[A2] : 0;
    // assign RD1 = regfile[A1];
    // assign RD2 = regfile[A2];

    // write is sequential
    always @(posedge clk) begin
        if (WE && A1!=0)
            regfile[A3] <= WD;
    end
endmodule