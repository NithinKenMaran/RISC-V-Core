`include "params.vh"

module decoder(
    input [31:0] instr,

    // register addresses
    output reg [4:0] rs2,
    output reg [4:0] rs1,
    output reg [4:0] rd,

    // operations
    output reg [3:0] alu_op,
    output [6:0] opcode,

    // register write enable
    output reg_write,
);
    // splitting instruction
    assign opcode = instr[6:0];
    assign r_funct7 = instr[31:25];
    assign r_funct3 = instr[14:12];

    // register signals
    always @(*) begin
        rs1 = 5'b0;
        rs2 = 5'b0;
        rd  = 5'b0;

        if (is_rtype) begin
            rs1 = instr[19:15];
            rs2 = instr[24:20];
            rd  = instr[11:7];
        end
        else if (is_itype) begin              
            rs1 = instr[19:15];               
            rd  = instr[11:7];                
            rs2 = 5'b0;                       
        end
    end

    // instruction (type) signals
    assign is_rtype = (opcode == 7'b0110011);
    assign is_itype = (opcode == 7'b0010011);

    // R-type instructions
    assign is_add  = is_rtype && (r_funct3 == 3'b000) && (r_funct7 == 7'b0000000);
    wire is_sub    = is_rtype && (r_funct3 == 3'b000) && (r_funct7 == 7'b0100000);
    wire is_sll    = is_rtype && (r_funct3 == 3'b001) && (r_funct7 == 7'b0000000);
    wire is_slt    = is_rtype && (r_funct3 == 3'b010) && (r_funct7 == 7'b0000000);
    wire is_sltu   = is_rtype && (r_funct3 == 3'b011) && (r_funct7 == 7'b0000000);
    wire is_xor    = is_rtype && (r_funct3 == 3'b100) && (r_funct7 == 7'b0000000);
    wire is_srl    = is_rtype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0000000);
    wire is_sra    = is_rtype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0100000);
    wire is_or     = is_rtype && (r_funct3 == 3'b110) && (r_funct7 == 7'b0000000);
    wire is_and    = is_rtype && (r_funct3 == 3'b111) && (r_funct7 == 7'b0000000);

    // I-type instructions
    wire is_addi   = is_itype && (r_funct3 == 3'b000);                                      
    wire is_slli   = is_itype && (r_funct3 == 3'b001) && (r_funct7 == 7'b0000000);         
    wire is_slti   = is_itype && (r_funct3 == 3'b010);                                      
    wire is_sltiu  = is_itype && (r_funct3 == 3'b011);                                      
    wire is_xori   = is_itype && (r_funct3 == 3'b100);                                      
    wire is_srli   = is_itype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0000000);         
    wire is_srai   = is_itype && (r_funct3 == 3'b101) && (r_funct7 == 7'b0100000);         
    wire is_ori    = is_itype && (r_funct3 == 3'b110);                                      
    wire is_andi   = is_itype && (r_funct3 == 3'b111);                                      

    // alu op
    always @(*) begin
        if (is_add || is_addi)         alu_op = `ALU_ADD;    
        else if (is_sub)               alu_op = `ALU_SUB;
        else if (is_sll || is_slli)    alu_op = `ALU_SLL;    // 
        else if (is_slt || is_slti)    alu_op = `ALU_SLT;    // 
        else if (is_sltu || is_sltiu)  alu_op = `ALU_SLTU;   // 
        else if (is_xor || is_xori)    alu_op = `ALU_XOR;    // 
        else if (is_srl || is_srli)    alu_op = `ALU_SRL;    // 
        else if (is_sra || is_srai)    alu_op = `ALU_SRA;    // 
        else if (is_or || is_ori)      alu_op = `ALU_OR;     // 
        else if (is_and || is_andi)    alu_op = `ALU_AND;    // 
        else                           alu_op = 4'b0;
    end

    // WRITE ENABLE FOR REGISTER
    assign reg_write = is_rtype || is_itype;              // 

endmodule // decoder