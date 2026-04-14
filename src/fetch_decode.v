`include "params.vh"
module rv32_fetch(
    input clk, rst,
    output reg [9:0] pc // need to change bit length
);

    // updating the instr_addr, PC is sequential. Current PC is latched.
    always @(posedge clk or posedge rst) begin
        if (rst)
            pc <= 0;
        else
            pc <= pc + 4;
    end

endmodule


// implements fetch and decode
// Takes in the instruction, slices it, 
// generates RF inputs, and control signals
module rv32_decoder # (
    parameter ADDR_LEN = 5
)(
    input [31:0] instr,
    input zero,

    // control signals generated,
    // main decoder
    output PCSrc,
    output reg ResultSrc,
    output reg MemWrite,
    output reg ALUSrc,
    output reg [1:0] ImmSrc,
    output reg RegWrite,

    // alu decoder
    output reg [2:0] ALUControl,

    // imm data
    output reg [11:0] imm,

    // RF addr
    output reg [ADDR_LEN-1:0] rs2,
    output reg [ADDR_LEN-1:0] rs1,
    output reg [ADDR_LEN-1:0] rd
);
    // op code for cases
    wire [6:0] op = instr[6:0];
    // required variables
    reg Branch;
    reg [2:0] f3;
    reg [6:0] funct7;
    reg [1:0] ALUOp;

    //  op, f3, funct7 are used to generate control signals
    // main decoder
    // based on the type of isntr, sets control signals
    always@(*) begin
        case(op)
            `OP_R_TYPE: begin
                // slicing
                rd = instr[11:7];
                f3 = instr[14:12];
                rs1 = instr[19:15];
                rs2 = instr[24:20];
                funct7 = instr[31:25];

                // control signals
                RegWrite = 1;
                // ImmSrc = ;
                ALUSrc = 0;
                MemWrite = 0; 
                ResultSrc = 0;
                Branch = 0;
                ALUOp = 2'b10;
            end

            `OP_I_TYPE: begin
                // slicing
                rd = instr[11:7];
                f3 = instr[14:12];
                rs1 = instr[19:15];
                imm = instr[31:20];

                // control signals
                RegWrite = 1;
                ImmSrc = 2'b00;
                ALUSrc = 1;
                MemWrite = 0; 
                ResultSrc = 0;
                Branch = 0;
                ALUOp = 2'b10;
            end

            `OP_B_TYPE: begin
                // slicing
                imm[3:0] = instr[11:8]; imm[10] = instr[7];
                f3 = instr[14:12];
                rs1 = instr[19:15];
                rs2 = instr[24:20];
                imm[11] = instr[31]; imm[10:5] = instr[30:25];
                // control signals
                RegWrite = 0;
                ImmSrc = 2'b10;
                ALUSrc = 0;
                MemWrite = 0; 
                // ResultSrc = ;
                Branch = 1;
                ALUOp = 2'b01;
                // NOTE:
                /* we get a bit shifterd verision of imm
                but here it's just shifted back. The extender will take care
                of this based on immsrc.
                */
            end
        endcase
    end

    ALU_decoder u_ALU_decoder(
        .op_5(op[5]), .f3(f3), .funct7_5(funct7[5]), .ALUOp(ALUOp),

        .ALUControl(ALUControl)
    );
    
    assign PCSrc = zero & Branch;
    

endmodule

// [4:0] x is a packed array, while x [4:0] is an unpacked array

module ALU_decoder(
    input op_5,
    input [2:0] f3,
    input funct7_5,
    input [1:0] ALUOp,

    output reg [2:0] ALUControl

);
    always@(*) begin
        case(ALUOp)
            2'b00: ALUControl = `ALU_ADD; //lw sw
            2'b01: ALUControl = `ALU_SUB; //beq
            2'b10: 
            begin
                case(f3)
                    3'b000: 
                    begin
                        if (op_5 && funct7_5)
                            ALUControl = `ALU_SUB;
                        else 
                            ALUControl = `ALU_ADD;
                    end
                    3'b010: ALUControl = `ALU_SLT;
                    3'b110: ALUControl = `ALU_OR;
                    3'b111: ALUControl = `ALU_AND;
                    default: ALUControl = `ALU_ADD; // just for safety
                endcase
            end
            default: ALUControl = `ALU_ADD; // just for safety
        endcase
    end


endmodule