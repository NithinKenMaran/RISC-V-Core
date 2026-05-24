// qspi_ctrl.v
//
// Assumptions:
// - Flash is already in the mode where a read transaction can be performed as:
//      24-bit address, dummy cycles, then 32-bit data.
// - PSRAMs are already in quad mode.
// - PSRAM command is sent in quad mode as 2 nibbles.
// - Addresses are 24-bit byte addresses.
// - Data transfers are 32-bit, MS-nibble first.
// - qspi_ctrl returns resp_valid for both reads and writes.
// - For writes, resp_valid means "write completed"; resp_rdata is 0.
//
// Target mapping expected by core.v:
//   2'b00: flash instruction memory
//   2'b01: register-file PSRAM
//   2'b10: data-memory PSRAM
//
// CS mapping:
//   qspi_cs_n[0] = flash
//   qspi_cs_n[1] = register-file PSRAM
//   qspi_cs_n[2] = data-memory PSRAM

module qspi_ctrl #(
    // Adjust these after checking the exact PSRAM / flash behavior.
    parameter [7:0] PSRAM_READ_CMD  = 8'hEB,
    parameter [7:0] PSRAM_WRITE_CMD = 8'h38,

    // Dummy cycles are counted in QSPI nibble cycles, not clk cycles.
    parameter integer FLASH_DUMMY_CYCLES       = 6,
    parameter integer PSRAM_READ_DUMMY_CYCLES  = 6,
    parameter integer PSRAM_WRITE_DUMMY_CYCLES = 0
)(
    input  wire        clk,
    input  wire        reset,

    input  wire        req_valid,
    output wire        req_ready,
    input  wire [1:0]  req_target,
    input  wire        req_write,
    input  wire [31:0] req_addr,
    input  wire [31:0] req_wdata,

    output wire        resp_valid,
    output wire [31:0] resp_rdata,

    output reg         qspi_sck,
    output reg  [2:0]  qspi_cs_n,
    inout  wire [3:0]  qspi_dq
);

    // ----------------------------
    // Target encoding
    // ----------------------------

    localparam TARGET_FLASH = 2'b00;
    localparam TARGET_REGS  = 2'b01;
    localparam TARGET_DMEM  = 2'b10;

    // ----------------------------
    // Main FSM states
    // ----------------------------

    localparam ST_IDLE     = 3'd0;
    localparam ST_NEXT_SEG = 3'd1;
    localparam ST_SHIFT    = 3'd2;
    localparam ST_DONE     = 3'd3;

    reg [2:0] state;

    // ----------------------------
    // Segment kinds
    // ----------------------------

    localparam SEG_NONE  = 3'd0;
    localparam SEG_SEND  = 3'd1;  // command/address/write data: drive DQ
    localparam SEG_DUMMY = 3'd2;  // dummy clocks: release DQ
    localparam SEG_READ  = 3'd3;  // read data: sample DQ

    reg [2:0] segment;

    // stage selects which segment comes next inside the current transaction.
    reg [2:0] stage;

    // phase 0: SCK low, setup output / release bus
    // phase 1: SCK high, sample input / complete nibble
    reg phase;

    reg [5:0] nibbles_left;
    reg [31:0] shift_reg;
    reg [31:0] read_shift;

    // Latched request.
    reg [1:0]  latched_target;
    reg        latched_write;
    reg [31:0] latched_addr;
    reg [31:0] latched_wdata;

    // DQ output control.
    reg [3:0] dq_out;
    reg       dq_oe;

    assign qspi_dq = dq_oe ? dq_out : 4'bzzzz;
    wire [3:0] dq_in = qspi_dq;

    reg        resp_valid_reg;
    reg [31:0] resp_rdata_reg;

    assign resp_valid = resp_valid_reg;
    assign resp_rdata = resp_rdata_reg;

    assign req_ready = (state == ST_IDLE);

    // ----------------------------
    // Helper wires
    // ----------------------------

    wire is_flash = (latched_target == TARGET_FLASH);
    wire is_psram = (latched_target == TARGET_REGS) ||
                    (latched_target == TARGET_DMEM);

    // ----------------------------
    // Main controller
    // ----------------------------

    always @(posedge clk) begin
        if (reset) begin
            state <= ST_IDLE;

            qspi_sck  <= 1'b0;
            qspi_cs_n <= 3'b111;

            dq_out <= 4'b0000;
            dq_oe  <= 1'b0;

            resp_valid_reg <= 1'b0;
            resp_rdata_reg <= 32'b0;

            latched_target <= TARGET_FLASH;
            latched_write  <= 1'b0;
            latched_addr   <= 32'b0;
            latched_wdata  <= 32'b0;

            segment <= SEG_NONE;
            stage <= 3'd0;
            phase <= 1'b0;
            nibbles_left <= 6'd0;
            shift_reg <= 32'b0;
            read_shift <= 32'b0;
        end else begin
            // Default: resp_valid is a one-cycle pulse.
            resp_valid_reg <= 1'b0;

            case (state)

                // ----------------------------
                // Wait for core request
                // ----------------------------

                ST_IDLE: begin
                    qspi_sck  <= 1'b0;
                    qspi_cs_n <= 3'b111;
                    dq_oe     <= 1'b0;
                    segment   <= SEG_NONE;
                    phase     <= 1'b0;

                    if (req_valid) begin
                        latched_target <= req_target;
                        latched_write  <= req_write;
                        latched_addr   <= req_addr;
                        latched_wdata  <= req_wdata;

                        read_shift <= 32'b0;
                        resp_rdata_reg <= 32'b0;

                        // Select target chip.
                        case (req_target)
                            TARGET_FLASH: qspi_cs_n <= 3'b110; // CS0 low
                            TARGET_REGS:  qspi_cs_n <= 3'b101; // CS1 low
                            TARGET_DMEM:  qspi_cs_n <= 3'b011; // CS2 low
                            default:       qspi_cs_n <= 3'b111;
                        endcase

                        stage <= 3'd0;
                        state <= ST_NEXT_SEG;
                    end
                end

                // ----------------------------
                // Choose the next transaction segment
                // ----------------------------

                ST_NEXT_SEG: begin
                    qspi_sck <= 1'b0;
                    dq_oe    <= 1'b0;
                    phase    <= 1'b0;

                    // FLASH read sequence:
                    //   stage 0: send 24-bit address
                    //   stage 1: dummy cycles
                    //   stage 2: read 32-bit data
                    //   stage 3: done
                    if (is_flash) begin
                        case (stage)
                            3'd0: begin
                                segment <= SEG_SEND;
                                shift_reg <= {latched_addr[23:0], 8'b0};
                                nibbles_left <= 6'd6;
                                stage <= 3'd1;
                                state <= ST_SHIFT;
                            end

                            3'd1: begin
                                if (FLASH_DUMMY_CYCLES == 0) begin
                                    stage <= 3'd2;
                                    state <= ST_NEXT_SEG;
                                end else begin
                                    segment <= SEG_DUMMY;
                                    nibbles_left <= FLASH_DUMMY_CYCLES[5:0];
                                    stage <= 3'd2;
                                    state <= ST_SHIFT;
                                end
                            end

                            3'd2: begin
                                segment <= SEG_READ;
                                nibbles_left <= 6'd8;
                                stage <= 3'd3;
                                state <= ST_SHIFT;
                            end

                            default: begin
                                state <= ST_DONE;
                            end
                        endcase
                    end

                    // PSRAM sequence:
                    // Read:
                    //   stage 0: send 8-bit read command
                    //   stage 1: send 24-bit address
                    //   stage 2: dummy cycles
                    //   stage 3: read 32-bit data
                    //   stage 4: done
                    //
                    // Write:
                    //   stage 0: send 8-bit write command
                    //   stage 1: send 24-bit address
                    //   stage 2: optional dummy cycles
                    //   stage 3: write 32-bit data
                    //   stage 4: done
                    else if (is_psram) begin
                        case (stage)
                            3'd0: begin
                                segment <= SEG_SEND;

                                if (latched_write) begin
                                    shift_reg <= {PSRAM_WRITE_CMD, 24'b0};
                                end else begin
                                    shift_reg <= {PSRAM_READ_CMD, 24'b0};
                                end

                                nibbles_left <= 6'd2;
                                stage <= 3'd1;
                                state <= ST_SHIFT;
                            end

                            3'd1: begin
                                segment <= SEG_SEND;
                                shift_reg <= {latched_addr[23:0], 8'b0};
                                nibbles_left <= 6'd6;
                                stage <= 3'd2;
                                state <= ST_SHIFT;
                            end

                            3'd2: begin
                                if (latched_write) begin
                                    if (PSRAM_WRITE_DUMMY_CYCLES == 0) begin
                                        stage <= 3'd3;
                                        state <= ST_NEXT_SEG;
                                    end else begin
                                        segment <= SEG_DUMMY;
                                        nibbles_left <= PSRAM_WRITE_DUMMY_CYCLES[5:0];
                                        stage <= 3'd3;
                                        state <= ST_SHIFT;
                                    end
                                end else begin
                                    if (PSRAM_READ_DUMMY_CYCLES == 0) begin
                                        stage <= 3'd3;
                                        state <= ST_NEXT_SEG;
                                    end else begin
                                        segment <= SEG_DUMMY;
                                        nibbles_left <= PSRAM_READ_DUMMY_CYCLES[5:0];
                                        stage <= 3'd3;
                                        state <= ST_SHIFT;
                                    end
                                end
                            end

                            3'd3: begin
                                if (latched_write) begin
                                    segment <= SEG_SEND;
                                    shift_reg <= latched_wdata;
                                    nibbles_left <= 6'd8;
                                    stage <= 3'd4;
                                    state <= ST_SHIFT;
                                end else begin
                                    segment <= SEG_READ;
                                    nibbles_left <= 6'd8;
                                    stage <= 3'd4;
                                    state <= ST_SHIFT;
                                end
                            end

                            default: begin
                                state <= ST_DONE;
                            end
                        endcase
                    end

                    // Unknown target: immediately acknowledge with zero.
                    else begin
                        state <= ST_DONE;
                    end
                end

                // ----------------------------
                // Shift one nibble per QSPI clock
                //
                // phase 0:
                //   SCK low
                //   drive output nibble or release bus
                //
                // phase 1:
                //   SCK high
                //   sample input nibble for reads
                //   decrement counter
                // ----------------------------

                ST_SHIFT: begin
                    if (phase == 1'b0) begin
                        qspi_sck <= 1'b0;

                        case (segment)
                            SEG_SEND: begin
                                dq_oe  <= 1'b1;
                                dq_out <= shift_reg[31:28];
                            end

                            SEG_DUMMY: begin
                                dq_oe  <= 1'b0;
                                dq_out <= 4'b0000;
                            end

                            SEG_READ: begin
                                dq_oe  <= 1'b0;
                                dq_out <= 4'b0000;
                            end

                            default: begin
                                dq_oe  <= 1'b0;
                                dq_out <= 4'b0000;
                            end
                        endcase

                        phase <= 1'b1;
                    end else begin
                        qspi_sck <= 1'b1;

                        if (segment == SEG_READ) begin
                            read_shift <= {read_shift[27:0], dq_in};
                        end

                        if (nibbles_left == 6'd1) begin
                            phase <= 1'b0;
                            // dq_oe is cleared in ST_NEXT_SEG. Releasing it here
                            // races with the posedge of qspi_sck: qspi_dq goes Z
                            // before the PMOD samples, corrupting the last nibble.
                            state <= ST_NEXT_SEG;
                        end else begin
                            nibbles_left <= nibbles_left - 6'd1;
                            shift_reg <= {shift_reg[27:0], 4'b0000};
                            phase <= 1'b0;
                        end
                    end
                end

                // ----------------------------
                // Finish transaction
                // ----------------------------

                ST_DONE: begin
                    qspi_sck  <= 1'b0;
                    qspi_cs_n <= 3'b111;
                    dq_oe     <= 1'b0;

                    if (latched_write) begin
                        resp_rdata_reg <= 32'b0;
                    end else begin
                        resp_rdata_reg <= read_shift;
                    end

                    resp_valid_reg <= 1'b1;
                    state <= ST_IDLE;
                end

                default: begin
                    state <= ST_IDLE;
                    qspi_sck <= 1'b0;
                    qspi_cs_n <= 3'b111;
                    dq_oe <= 1'b0;
                end

            endcase
        end
    end

endmodule