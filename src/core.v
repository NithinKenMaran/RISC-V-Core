`include "params.vh"
// `define DEBUG

module core(
    input  wire clk,
    input  wire reset,

    // External QSPI pins. Goes to QSPI PMOD.
    output wire       qspi_sck,
    output wire [2:0] qspi_cs_n,
    inout  wire [3:0] qspi_dq
);

    // Fixed hardware trap vector (terminal, no mret).
    // Reserves 0xF000..0xFFFF for trap/debug code in the 64 KiB flash.
    localparam [31:0] TRAP_VECTOR = 32'h0000_F000;

    // Abstract targets understood by qspi_ctrl.
    localparam TARGET_FLASH = 2'b00;  // instruction memory
    localparam TARGET_REGS  = 2'b01;  // external register file in PSRAM
    localparam TARGET_DMEM  = 2'b10;  // external data memory in PSRAM

    // Core FSM states.
    localparam S_FETCH_REQ          = 4'd0;
    localparam S_FETCH_WAIT         = 4'd1;
    localparam S_DECODE             = 4'd2;
    localparam S_RS1_REQ            = 4'd3;
    localparam S_RS1_WAIT           = 4'd4;
    localparam S_RS2_REQ            = 4'd5;
    localparam S_RS2_WAIT           = 4'd6;
    localparam S_EXECUTE            = 4'd7;
    localparam S_MEM_REQ            = 4'd8;
    localparam S_MEM_WAIT           = 4'd9;
    localparam S_WB_REQ             = 4'd10;
    localparam S_WB_WAIT            = 4'd11;
    localparam S_PC_UPDATE          = 4'd12;
    localparam S_MEM_RMW_WRITE_REQ  = 4'd13;
    localparam S_MEM_RMW_WRITE_WAIT = 4'd14;

    reg [3:0] state;

    // Internal architectural / temporary state.
    reg [31:0] pc;
    reg [31:0] instr_reg;
    reg [31:0] rs1_data;
    reg [31:0] rs2_data;
    reg [31:0] alu_result_reg;
    reg [31:0] mem_rdata_reg;

    // Trap state registers (no CSRs; terminal trap only).
    // Accessible via cocotb as dut.dut.trap_valid etc.
    reg        trap_valid;
    reg [31:0] trap_epc;
    reg [31:0] trap_cause;
    reg [31:0] trap_tval;

    // Set whenever we should redirect to TRAP_VECTOR in S_PC_UPDATE.
    reg        trap_pending;

    // RMW (read-modify-write) state for SB/SH.
    reg        rmw_in_progress;
    reg [31:0] rmw_old_word;

    // QSPI request/response interface.
    reg         qspi_req_valid;
    wire        qspi_req_ready;
    reg  [1:0]  qspi_req_target;
    reg         qspi_req_write;
    reg  [31:0] qspi_req_addr;
    reg  [31:0] qspi_req_wdata;
    wire        qspi_resp_valid;
    wire [31:0] qspi_resp_rdata;

    qspi_ctrl qspi_ctrl_inst (
        .clk(clk),
        .reset(reset),

        .req_valid(qspi_req_valid),
        .req_ready(qspi_req_ready),
        .req_target(qspi_req_target),
        .req_write(qspi_req_write),
        .req_addr(qspi_req_addr),
        .req_wdata(qspi_req_wdata),

        .resp_valid(qspi_resp_valid),
        .resp_rdata(qspi_resp_rdata),

        .qspi_sck(qspi_sck),
        .qspi_cs_n(qspi_cs_n),
        .qspi_dq(qspi_dq)
    );

    // Decode current latched instruction.
    wire [6:0]  op;
    wire [2:0]  funct3;
    wire        funct7_5;
    wire [4:0]  rs1;
    wire [4:0]  rs2;
    wire [4:0]  rd;
    wire [24:0] imm;
    wire        dec_is_ecall;
    wire        dec_is_ebreak;

    decoder decoder_inst (
        .instr(instr_reg),
        .op(op),
        .funct3(funct3),
        .funct7_5(funct7_5),
        .rs1(rs1),
        .rs2(rs2),
        .rd(rd),
        .imm(imm),
        .is_ecall(dec_is_ecall),
        .is_ebreak(dec_is_ebreak)
    );

    // Branch/compare values.
    wire cmp_zero = (rs1_data == rs2_data);
    wire cmp_lt   = ($signed(rs1_data) < $signed(rs2_data));
    wire cmp_ltu  = (rs1_data < rs2_data);

    // Control signals.
    wire [1:0] pc_src;
    wire [2:0] result_src;
    wire       mem_read;
    wire       mem_write;
    wire [3:0] alu_op;
    wire       alu_src;
    wire [2:0] imm_src;
    wire       reg_write;

    wire uses_rs1;
    wire uses_rs2;
    wire is_load;
    wire is_store;
    wire is_branch;
    wire is_jal;
    wire is_jalr;
    wire is_trap_instr;
    wire is_sb;
    wire is_sh;
    wire is_fence;
    wire is_illegal;

    control_unit control_unit_inst (
        .op(op),
        .funct3(funct3),
        .funct7_5(funct7_5),

        .zero(cmp_zero),
        .lt(cmp_lt),
        .ltu(cmp_ltu),

        .is_ecall(dec_is_ecall),
        .is_ebreak(dec_is_ebreak),

        .pc_src(pc_src),
        .result_src(result_src),

        .mem_read(mem_read),
        .mem_write(mem_write),

        .alu_op(alu_op),
        .alu_src(alu_src),

        .imm_src(imm_src),
        .reg_write(reg_write),

        .uses_rs1(uses_rs1),
        .uses_rs2(uses_rs2),
        .is_load(is_load),
        .is_store(is_store),
        .is_branch(is_branch),
        .is_jal(is_jal),
        .is_jalr(is_jalr),
        .is_trap_instr(is_trap_instr),

        .is_sb(is_sb),
        .is_sh(is_sh),
        .is_fence(is_fence),
        .is_illegal(is_illegal)
    );

    // Immediate extender.
    wire [31:0] imm_ext;

    extender extender_inst (
        .imm(imm),
        .imm_src(imm_src),
        .imm_ext(imm_ext)
    );

    // ALU.
    wire [31:0] alu_src_a;
    wire [31:0] alu_src_b;
    wire [31:0] alu_result;

    assign alu_src_a = rs1_data;
    assign alu_src_b = alu_src ? imm_ext : rs2_data;

    alu alu_inst (
        .alu_op(alu_op),
        .a(alu_src_a),
        .b(alu_src_b),
        .result(alu_result)
    );

    // Writeback data mux.
    reg [31:0] wb_data;

    always @(*) begin
        case (result_src)
            3'b000: wb_data = alu_result_reg;  // ALU result
            3'b001: wb_data = mem_rdata_reg;   // load result (already extracted)
            3'b010: wb_data = pc + 32'd4;      // JAL/JALR link
            3'b011: wb_data = imm_ext;         // LUI
            3'b100: wb_data = pc + imm_ext;    // AUIPC
            default: wb_data = 32'b0;
        endcase
    end

    // Next PC mux.
    reg [31:0] pc_next;

    always @(*) begin
        case (pc_src)
            2'b00: pc_next = pc + 32'd4;
            2'b01: pc_next = pc + imm_ext;
            2'b10: pc_next = (rs1_data + imm_ext) & 32'hFFFF_FFFE;
            default: pc_next = pc + 32'd4;
        endcase
    end

    // External register-file address mapping.
    wire [31:0] rs1_qspi_addr;
    wire [31:0] rs2_qspi_addr;
    wire [31:0] rd_qspi_addr;

    assign rs1_qspi_addr = {25'b0, rs1, 2'b00};
    assign rs2_qspi_addr = {25'b0, rs2, 2'b00};
    assign rd_qspi_addr  = {25'b0, rd,  2'b00};

    // Combinational merge word for SB/SH read-modify-write.
    // Uses little-endian byte ordering: effective_addr[1:0]==0 -> bits[7:0].
    reg [31:0] merge_word;

    always @(*) begin
        if (is_sh) begin
            case (alu_result_reg[1])
                1'b0: merge_word = {rmw_old_word[31:16], rs2_data[15:0]};
                1'b1: merge_word = {rs2_data[15:0], rmw_old_word[15:0]};
                default: merge_word = rmw_old_word;
            endcase
        end else begin
            // SB
            case (alu_result_reg[1:0])
                2'b00: merge_word = {rmw_old_word[31:8],  rs2_data[7:0]};
                2'b01: merge_word = {rmw_old_word[31:16], rs2_data[7:0], rmw_old_word[7:0]};
                2'b10: merge_word = {rmw_old_word[31:24], rs2_data[7:0], rmw_old_word[15:0]};
                2'b11: merge_word = {rs2_data[7:0], rmw_old_word[23:0]};
                default: merge_word = rmw_old_word;
            endcase
        end
    end

    // Main sequencer.
    always @(posedge clk) begin
        if (reset) begin
            state          <= S_FETCH_REQ;
            pc             <= 32'b0;
            instr_reg      <= 32'b0;
            rs1_data       <= 32'b0;
            rs2_data       <= 32'b0;
            alu_result_reg <= 32'b0;
            mem_rdata_reg  <= 32'b0;

            trap_valid   <= 1'b0;
            trap_epc     <= 32'b0;
            trap_cause   <= 32'b0;
            trap_tval    <= 32'b0;
            trap_pending <= 1'b0;

            rmw_in_progress <= 1'b0;
            rmw_old_word    <= 32'b0;

            qspi_req_valid  <= 1'b0;
            qspi_req_target <= TARGET_FLASH;
            qspi_req_write  <= 1'b0;
            qspi_req_addr   <= 32'b0;
            qspi_req_wdata  <= 32'b0;
        end else begin
            case (state)

                S_FETCH_REQ: begin
                    qspi_req_valid  <= 1'b1;
                    qspi_req_target <= TARGET_FLASH;
                    qspi_req_write  <= 1'b0;
                    qspi_req_addr   <= pc;
                    qspi_req_wdata  <= 32'b0;

                    if (qspi_req_valid && qspi_req_ready) begin
                        qspi_req_valid <= 1'b0;
                        state <= S_FETCH_WAIT;
                    end
                end

                S_FETCH_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        instr_reg <= qspi_resp_rdata;
                        state <= S_DECODE;
                    end
                end

                S_DECODE: begin
                    // Decode is combinational from instr_reg.
                    if (is_trap_instr) begin
                        trap_valid   <= 1'b1;
                        trap_epc     <= pc;
                        trap_cause   <= dec_is_ecall ? 32'd11 : 32'd3;
                        trap_tval    <= instr_reg;
                        trap_pending <= 1'b1;
                        state        <= S_PC_UPDATE;
                    end else if (is_illegal) begin
                        trap_valid   <= 1'b1;
                        trap_epc     <= pc;
                        trap_cause   <= 32'd2;  // illegal instruction
                        trap_tval    <= instr_reg;
                        trap_pending <= 1'b1;
                        state        <= S_PC_UPDATE;
                    end else if (is_fence) begin
                        // FENCE: NOP, advance PC normally
                        state <= S_PC_UPDATE;
                    end else begin
                        state <= S_RS1_REQ;
                    end
                end

                S_RS1_REQ: begin
                    if (!uses_rs1 || (rs1 == 5'd0)) begin
                        rs1_data       <= 32'b0;
                        qspi_req_valid <= 1'b0;
                        state <= S_RS2_REQ;
                    end else begin
                        qspi_req_valid  <= 1'b1;
                        qspi_req_target <= TARGET_REGS;
                        qspi_req_write  <= 1'b0;
                        qspi_req_addr   <= rs1_qspi_addr;
                        qspi_req_wdata  <= 32'b0;

                        if (qspi_req_valid && qspi_req_ready) begin
                            qspi_req_valid <= 1'b0;
                            state <= S_RS1_WAIT;
                        end
                    end
                end

                S_RS1_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        rs1_data <= qspi_resp_rdata;
                        state <= S_RS2_REQ;
                    end
                end

                S_RS2_REQ: begin
                    if (!uses_rs2 || (rs2 == 5'd0)) begin
                        rs2_data       <= 32'b0;
                        qspi_req_valid <= 1'b0;
                        state <= S_EXECUTE;
                    end else begin
                        qspi_req_valid  <= 1'b1;
                        qspi_req_target <= TARGET_REGS;
                        qspi_req_write  <= 1'b0;
                        qspi_req_addr   <= rs2_qspi_addr;
                        qspi_req_wdata  <= 32'b0;

                        if (qspi_req_valid && qspi_req_ready) begin
                            qspi_req_valid <= 1'b0;
                            state <= S_RS2_WAIT;
                        end
                    end
                end

                S_RS2_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        rs2_data <= qspi_resp_rdata;
                        state <= S_EXECUTE;
                    end
                end

                S_EXECUTE: begin
                    alu_result_reg <= alu_result;
                    state <= S_MEM_REQ;
                end

                S_MEM_REQ: begin
                    if (mem_read) begin
                        // Load path: LB / LH / LW / LBU / LHU
                        // Check alignment before issuing the QSPI request.
                        if (((funct3 == 3'b001) || (funct3 == 3'b101)) && alu_result_reg[0]) begin
                            // LH / LHU misaligned (odd address)
                            trap_valid   <= 1'b1;
                            trap_epc     <= pc;
                            trap_cause   <= 32'd4;  // load address misaligned
                            trap_tval    <= alu_result_reg;
                            trap_pending <= 1'b1;
                            state        <= S_PC_UPDATE;
                        end else if ((funct3 == 3'b010) && (alu_result_reg[1:0] != 2'b00)) begin
                            // LW misaligned
                            trap_valid   <= 1'b1;
                            trap_epc     <= pc;
                            trap_cause   <= 32'd4;
                            trap_tval    <= alu_result_reg;
                            trap_pending <= 1'b1;
                            state        <= S_PC_UPDATE;
                        end else begin
                            // Aligned (or byte-addressed) load: read aligned 32-bit word.
                            qspi_req_valid  <= 1'b1;
                            qspi_req_target <= TARGET_DMEM;
                            qspi_req_write  <= 1'b0;
                            qspi_req_addr   <= {alu_result_reg[31:2], 2'b00};
                            qspi_req_wdata  <= 32'b0;

                            if (qspi_req_valid && qspi_req_ready) begin
                                qspi_req_valid <= 1'b0;
                                state <= S_MEM_WAIT;
                            end
                        end
                    end else if (is_sb) begin
                        // SB: byte-addressable, always valid alignment. Issue RMW read.
                        qspi_req_valid  <= 1'b1;
                        qspi_req_target <= TARGET_DMEM;
                        qspi_req_write  <= 1'b0;
                        qspi_req_addr   <= {alu_result_reg[31:2], 2'b00};
                        qspi_req_wdata  <= 32'b0;
                        rmw_in_progress <= 1'b1;

                        if (qspi_req_valid && qspi_req_ready) begin
                            qspi_req_valid <= 1'b0;
                            state <= S_MEM_WAIT;
                        end
                    end else if (is_sh) begin
                        // SH: requires halfword alignment.
                        if (alu_result_reg[0]) begin
                            trap_valid   <= 1'b1;
                            trap_epc     <= pc;
                            trap_cause   <= 32'd6;  // store address misaligned
                            trap_tval    <= alu_result_reg;
                            trap_pending <= 1'b1;
                            state        <= S_PC_UPDATE;
                        end else begin
                            // Aligned SH: issue RMW read.
                            qspi_req_valid  <= 1'b1;
                            qspi_req_target <= TARGET_DMEM;
                            qspi_req_write  <= 1'b0;
                            qspi_req_addr   <= {alu_result_reg[31:2], 2'b00};
                            qspi_req_wdata  <= 32'b0;
                            rmw_in_progress <= 1'b1;

                            if (qspi_req_valid && qspi_req_ready) begin
                                qspi_req_valid <= 1'b0;
                                state <= S_MEM_WAIT;
                            end
                        end
                    end else if (mem_write) begin
                        // SW: requires word alignment.
                        if (alu_result_reg[1:0] != 2'b00) begin
                            trap_valid   <= 1'b1;
                            trap_epc     <= pc;
                            trap_cause   <= 32'd6;
                            trap_tval    <= alu_result_reg;
                            trap_pending <= 1'b1;
                            state        <= S_PC_UPDATE;
                        end else begin
                            qspi_req_valid  <= 1'b1;
                            qspi_req_target <= TARGET_DMEM;
                            qspi_req_write  <= 1'b1;
                            qspi_req_addr   <= alu_result_reg;
                            qspi_req_wdata  <= rs2_data;

                            if (qspi_req_valid && qspi_req_ready) begin
                                qspi_req_valid <= 1'b0;
                                state <= S_MEM_WAIT;
                            end
                        end
                    end else begin
                        qspi_req_valid <= 1'b0;
                        state <= S_WB_REQ;
                    end
                end

                S_MEM_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        if (rmw_in_progress) begin
                            // RMW read phase complete: latch old word, move to write phase.
                            rmw_old_word    <= qspi_resp_rdata;
                            rmw_in_progress <= 1'b0;
                            state <= S_MEM_RMW_WRITE_REQ;
                        end else if (mem_read) begin
                            // Load complete: extract byte/halfword (little-endian).
                            case (funct3)
                                3'b010: begin  // LW
                                    mem_rdata_reg <= qspi_resp_rdata;
                                end
                                3'b000: begin  // LB (sign-extend)
                                    case (alu_result_reg[1:0])
                                        2'b00: mem_rdata_reg <= {{24{qspi_resp_rdata[7]}},  qspi_resp_rdata[7:0]};
                                        2'b01: mem_rdata_reg <= {{24{qspi_resp_rdata[15]}}, qspi_resp_rdata[15:8]};
                                        2'b10: mem_rdata_reg <= {{24{qspi_resp_rdata[23]}}, qspi_resp_rdata[23:16]};
                                        2'b11: mem_rdata_reg <= {{24{qspi_resp_rdata[31]}}, qspi_resp_rdata[31:24]};
                                        default: mem_rdata_reg <= 32'b0;
                                    endcase
                                end
                                3'b100: begin  // LBU (zero-extend)
                                    case (alu_result_reg[1:0])
                                        2'b00: mem_rdata_reg <= {24'b0, qspi_resp_rdata[7:0]};
                                        2'b01: mem_rdata_reg <= {24'b0, qspi_resp_rdata[15:8]};
                                        2'b10: mem_rdata_reg <= {24'b0, qspi_resp_rdata[23:16]};
                                        2'b11: mem_rdata_reg <= {24'b0, qspi_resp_rdata[31:24]};
                                        default: mem_rdata_reg <= 32'b0;
                                    endcase
                                end
                                3'b001: begin  // LH (sign-extend)
                                    case (alu_result_reg[1])
                                        1'b0: mem_rdata_reg <= {{16{qspi_resp_rdata[15]}}, qspi_resp_rdata[15:0]};
                                        1'b1: mem_rdata_reg <= {{16{qspi_resp_rdata[31]}}, qspi_resp_rdata[31:16]};
                                        default: mem_rdata_reg <= 32'b0;
                                    endcase
                                end
                                3'b101: begin  // LHU (zero-extend)
                                    case (alu_result_reg[1])
                                        1'b0: mem_rdata_reg <= {16'b0, qspi_resp_rdata[15:0]};
                                        1'b1: mem_rdata_reg <= {16'b0, qspi_resp_rdata[31:16]};
                                        default: mem_rdata_reg <= 32'b0;
                                    endcase
                                end
                                default: mem_rdata_reg <= qspi_resp_rdata;
                            endcase
                            state <= S_WB_REQ;
                        end else begin
                            // SW write ack: no data to latch.
                            state <= S_WB_REQ;
                        end
                    end
                end

                S_MEM_RMW_WRITE_REQ: begin
                    // Issue the write back with the merged word.
                    // merge_word is computed combinationally from rmw_old_word, rs2_data,
                    // funct3 (is_sh vs is_sb), and alu_result_reg[1:0].
                    qspi_req_valid  <= 1'b1;
                    qspi_req_target <= TARGET_DMEM;
                    qspi_req_write  <= 1'b1;
                    qspi_req_addr   <= {alu_result_reg[31:2], 2'b00};
                    qspi_req_wdata  <= merge_word;

                    if (qspi_req_valid && qspi_req_ready) begin
                        qspi_req_valid <= 1'b0;
                        state <= S_MEM_RMW_WRITE_WAIT;
                    end
                end

                S_MEM_RMW_WRITE_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        state <= S_WB_REQ;
                    end
                end

                S_WB_REQ: begin
                    if (reg_write && (rd != 5'd0)) begin
                        qspi_req_valid  <= 1'b1;
                        qspi_req_target <= TARGET_REGS;
                        qspi_req_write  <= 1'b1;
                        qspi_req_addr   <= rd_qspi_addr;
                        qspi_req_wdata  <= wb_data;

                        if (qspi_req_valid && qspi_req_ready) begin
                            qspi_req_valid <= 1'b0;
                            state <= S_WB_WAIT;
                        end
                    end else begin
                        qspi_req_valid <= 1'b0;
                        state <= S_PC_UPDATE;
                    end
                end

                S_WB_WAIT: begin
                    qspi_req_valid <= 1'b0;

                    if (qspi_resp_valid) begin
                        state <= S_PC_UPDATE;
                    end
                end

                S_PC_UPDATE: begin
                    pc           <= trap_pending ? TRAP_VECTOR : pc_next;
                    trap_pending <= 1'b0;
                    qspi_req_valid <= 1'b0;
                    state <= S_FETCH_REQ;
                end

                default: begin
                    qspi_req_valid <= 1'b0;
                    state <= S_FETCH_REQ;
                end

            endcase
        end
    end

endmodule
