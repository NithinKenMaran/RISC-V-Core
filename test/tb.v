`include "params.vh"

module testbench;
    reg clk, reset;
    reg [`XLEN-1:0] instr;

    riscv dut(clk, reset, instr);
    
    initial begin
        $monitor("t=%t, x1=%d, x2=%d, x3=%d, x4=%d",
                    $time, 
                    dut.rf.registers[1], 
                    dut.rf.registers[2],
                    dut.rf.registers[3],
                    dut.rf.registers[4]);
        $dumpfile("riscv.vcd");
        $dumpvars(0, testbench);
        #20 $finish;
    end

    initial begin
        clk = 0;
        reset = 1;
        #2 reset = 0;
        #1 instr = 32'b0000000_00010_00001_000_00011_0110011;
        #10 instr = 32'b0000000_00010_00001_000_00100_0110011; 
    end

    initial begin
        dut.rf.registers[1] = 10;
        dut.rf.registers[2] = 20;
        #12 dut.rf.registers[2] = 10;
    end

    always #5 clk = ~clk;

endmodule