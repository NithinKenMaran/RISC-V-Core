module imem # (
    parameter WORD_LEN = 32,
    parameter ARR_LEN = 1024
    // 4kb memory
)
(
    input [31:0] instr_addr,

    output [31:0] instr

);
    reg [WORD_LEN-1:0] mem [0:ARR_LEN-1];
    initial $readmemh("prog_instr.hex", mem);
    assign instr = mem[instr_addr];

endmodule