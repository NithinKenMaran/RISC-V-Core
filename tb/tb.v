`timescale 1ns/1ns
`include "tb/instructions.vh"

module tb;

    // ----------------------------
    // Instruction memory
    // ----------------------------
    reg [31:0] imem [0:255];

    // ----------------------------
    // Signals
    // ----------------------------
    reg clk;
    reg rst;
    wire [9:0] pc;
    wire [31:0] instr;

    // ----------------------------
    // DUT
    // ----------------------------
    rv32_core dut (
        .clk(clk),
        .rst(rst),
        .instr(instr),
        .pc(pc)
    );

    // ----------------------------
    // Clock
    // ----------------------------
    always #5 clk = ~clk;

    // ----------------------------
    // Instruction fetch;
    // basically, we expose PC in fetch module as an output,
    // and use it to obtain instr, and feed it back to our DUT as an input.
    // ----------------------------
    assign instr = imem[pc >> 2];

    // ----------------------------
    // Test sequence
    // ----------------------------
    integer i;

    initial begin
        clk = 0;
        rst = 1;

        // Initialize memory with NOPs
        for (i = 0; i < 256; i = i + 1)
            imem[i] = 32'h00000013;

        // Load program
        imem[1] = `ADD_R3_R2_R1;
        imem[2] = `ADDI_3_R1_R5;
        // Preload registers
        dut.u_regfile.regfile[2] = 32'd10;
        dut.u_regfile.regfile[3] = 32'd20;

        // Reset phase
        repeat (1) @(posedge clk);
        #1
        rst = 0;

        // Run program
        repeat (3) @(posedge clk);
        // 1 for NOP, 
        // 2 for ADD, 3 for ADDI
        #1 // wait for write
        // Check result
        if (dut.u_regfile.regfile[5] == 32'd33) begin
            $display("PASS");
            // $display("t=%0t pc=%0d instr=%h r2=%0d r3=%0d r1=%0d",
            // $time, pc, instr, dut.u_regfile.regfile[2],
            // dut.u_regfile.regfile[3], dut.u_regfile.regfile[1]);
        end
        else begin
            $display("FAIL: rd (R1) = %0d", dut.u_regfile.regfile[1]);
        end
        repeat (1) @(posedge clk)

        #5 $finish;
    end

    // ----------------------------
    // Debug
    // ----------------------------
    always @(posedge clk) begin
        #1
        $display("t=%0t pc=%0d instr=%h ImmExt=%0d r1=%0d r2=%0d r3=%0d r5=%0d",
            $time, pc, instr, dut.ImmExt,
            dut.u_regfile.regfile[1], dut.u_regfile.regfile[2],
            dut.u_regfile.regfile[3], dut.u_regfile.regfile[5]);
    end

endmodule

