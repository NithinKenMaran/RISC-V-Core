`timescale 1ns/1ps

// qspi_pmod.v
//
// Simulation-only behavioral model of the TinyTapeout QSPI PMOD board.
// It models:
//   CS0 -> flash
//   CS1 -> PSRAM A
//   CS2 -> PSRAM B
//
// The model intentionally contains two layers:
//   1. pre-init SPI-ish behavior used by an RP2040-style setup sequence
//   2. post-init runtime behavior used by core/qspi_ctrl
//
// Runtime mode expected by the current qspi_ctrl.v:
//   Flash continuous read:
//       CS0 low, 24-bit QPI address, dummy nibbles, streaming data
//   PSRAM QPI read:
//       CS1/CS2 low, QPI cmd 0xEB or 0x0B, 24-bit address, dummy nibbles, data
//   PSRAM QPI write:
//       CS1/CS2 low, QPI cmd 0x38 or 0x02, 24-bit address, data
//
// Hex files are byte-addressed, one byte per line:
//   +FLASH_HEX=test/mem/flash.hex
//   +RAMA_HEX=test/mem/rama.hex
//   +RAMB_HEX=test/mem/ramb.hex
//
// Optional fast-start mode plusargs:
//   +FLASH_CONTINUOUS=1
//   +RAMA_QPI=1
//   +RAMB_QPI=1

module qspi_pmod #(
    parameter integer FLASH_BYTES = 1 << 16,
    parameter integer RAMA_BYTES  = 1 << 16,
    parameter integer RAMB_BYTES  = 1 << 16,
    parameter integer VERBOSE     = 0,

    // Match the current qspi_ctrl.v defaults.
    parameter integer FLASH_CONT_DUMMY_NIBBLES = 6,
    parameter integer PSRAM_QPI_DUMMY_NIBBLES  = 6
)(
    input  wire       qspi_sck,
    input  wire [2:0] qspi_cs_n,
    inout  wire [3:0] qspi_dq
);

    localparam DEV_NONE  = 2'd0;
    localparam DEV_FLASH = 2'd1;
    localparam DEV_RAMA  = 2'd2;
    localparam DEV_RAMB  = 2'd3;

    localparam ST_IDLE          = 5'd0;

    // Runtime QPI/continuous states.
    localparam ST_QPI_CMD       = 5'd1;
    localparam ST_QPI_ADDR      = 5'd2;
    localparam ST_QPI_DUMMY     = 5'd3;
    localparam ST_QPI_RDATA     = 5'd4;
    localparam ST_QPI_WDATA     = 5'd5;

    // Pre-init SPI states.
    localparam ST_SPI_CMD       = 5'd6;
    localparam ST_SPI_ADDR      = 5'd7;
    localparam ST_SPI_DUMMY     = 5'd8;
    localparam ST_SPI_RDATA     = 5'd9;
    localparam ST_SPI_WDATA     = 5'd10;
    localparam ST_SPI_ID        = 5'd11;
    localparam ST_SPI_STATUS    = 5'd12;

    reg [7:0] flash [0:FLASH_BYTES-1];
    reg [7:0] ram_a [0:RAMA_BYTES-1];
    reg [7:0] ram_b [0:RAMB_BYTES-1];

    reg [3:0] dq_out;
    reg       dq_oe;
    assign qspi_dq = dq_oe ? dq_out : 4'bzzzz;

    reg [1:0] selected_dev;
    reg [4:0] state;

    reg flash_continuous_mode;
    reg flash_write_enable;
    reg ram_a_qpi_mode;
    reg ram_b_qpi_mode;

    reg [7:0]  cmd;
    reg [23:0] addr;
    reg [7:0]  byte_buf;
    reg [7:0]  id_buf;
    reg [5:0]  bit_count;
    reg [5:0]  nib_count;
    reg [5:0]  dummy_left;
    reg        low_nibble_phase;
    reg [3:0]  spi_out_shift;
    reg [2:0]  id_index;

    integer i;
    integer sector_base;

    integer plusval;

    initial begin
        for (i = 0; i < FLASH_BYTES; i = i + 1) flash[i] = 8'h00;
        for (i = 0; i < RAMA_BYTES;  i = i + 1) ram_a[i]  = 8'h00;
        for (i = 0; i < RAMB_BYTES;  i = i + 1) ram_b[i]  = 8'h00;

        // Icarus Verilog's $value$plusargs stores the full "+KEY=value" string
        // (including the + prefix) into variables, so $readmemh would receive an
        // invalid filename. Use fixed relative paths instead; vvp runs from test/.
        $readmemh("mem/flash.hex", flash);
        $readmemh("mem/rama.hex",  ram_a);
        $readmemh("mem/ramb.hex",  ram_b);

        flash_continuous_mode = 1'b0;
        ram_a_qpi_mode        = 1'b0;
        ram_b_qpi_mode        = 1'b0;

        if ($value$plusargs("FLASH_CONTINUOUS=%d", plusval)) flash_continuous_mode = (plusval != 0);
        if ($value$plusargs("RAMA_QPI=%d", plusval))         ram_a_qpi_mode        = (plusval != 0);
        if ($value$plusargs("RAMB_QPI=%d", plusval))         ram_b_qpi_mode        = (plusval != 0);

        flash_write_enable = 1'b0;

        selected_dev = DEV_NONE;
        state = ST_IDLE;
        cmd = 8'h00;
        addr = 24'h0;
        byte_buf = 8'h00;
        id_buf = 8'h00;
        bit_count = 0;
        nib_count = 0;
        dummy_left = 0;
        low_nibble_phase = 0;
        spi_out_shift = 0;
        id_index = 0;
        dq_out = 4'h0;
        dq_oe = 1'b0;
    end

    function is_ram_qpi;
        input [1:0] dev;
        begin
            if (dev == DEV_RAMA) is_ram_qpi = ram_a_qpi_mode;
            else if (dev == DEV_RAMB) is_ram_qpi = ram_b_qpi_mode;
            else is_ram_qpi = 1'b0;
        end
    endfunction

    function [7:0] mem_read_byte;
        input [1:0]  dev;
        input [23:0] a;
        begin
            case (dev)
                DEV_FLASH: mem_read_byte = flash[a % FLASH_BYTES];
                DEV_RAMA:  mem_read_byte = ram_a [a % RAMA_BYTES];
                DEV_RAMB:  mem_read_byte = ram_b [a % RAMB_BYTES];
                default:   mem_read_byte = 8'h00;
            endcase
        end
    endfunction

    task mem_write_byte;
        input [1:0]  dev;
        input [23:0] a;
        input [7:0]  v;
        begin
            case (dev)
                DEV_FLASH: begin
                    if (flash_write_enable) flash[a % FLASH_BYTES] = v;
                end
                DEV_RAMA: ram_a[a % RAMA_BYTES] = v;
                DEV_RAMB: ram_b[a % RAMB_BYTES] = v;
                default: ;
            endcase
        end
    endtask

    task erase_flash_sector_4k;
        input [23:0] a;
        begin
            if (flash_write_enable) begin
                sector_base = (a & 24'hFFF000);
                for (i = 0; i < 4096; i = i + 1) begin
                    if ((sector_base + i) < FLASH_BYTES) flash[sector_base + i] = 8'hFF;
                end
                flash_write_enable = 1'b0;
            end
        end
    endtask

    task set_selected;
        input [1:0] dev;
        begin
            selected_dev = dev;
            dq_oe = 1'b0;
            dq_out = 4'h0;
            cmd = 8'h00;
            addr = 24'h0;
            byte_buf = 8'h00;
            bit_count = 0;
            nib_count = 0;
            dummy_left = 0;
            low_nibble_phase = 1'b0;
            id_index = 0;

            if (dev == DEV_FLASH && flash_continuous_mode) begin
                state = ST_QPI_ADDR;   // no command byte in current qspi_ctrl runtime
            end else if ((dev == DEV_RAMA || dev == DEV_RAMB) && is_ram_qpi(dev)) begin
                state = ST_QPI_CMD;
            end else begin
                state = ST_SPI_CMD;
            end
        end
    endtask

    task deselect;
        begin
            dq_oe = 1'b0;
            dq_out = 4'h0;
            selected_dev = DEV_NONE;
            state = ST_IDLE;
            bit_count = 0;
            nib_count = 0;
            dummy_left = 0;
            low_nibble_phase = 0;
        end
    endtask

    always @(negedge qspi_cs_n[0]) set_selected(DEV_FLASH);
    always @(negedge qspi_cs_n[1]) set_selected(DEV_RAMA);
    always @(negedge qspi_cs_n[2]) set_selected(DEV_RAMB);

    always @(posedge qspi_cs_n[0] or posedge qspi_cs_n[1] or posedge qspi_cs_n[2]) begin
        if (qspi_cs_n == 3'b111) deselect();
    end

    // Input side: sample controller/host outputs on rising SCK.
    always @(posedge qspi_sck) begin
        if (selected_dev != DEV_NONE) begin
            case (state)
                ST_QPI_CMD: begin
                    cmd <= {cmd[3:0], qspi_dq};
                    if (nib_count == 1) begin
                        cmd <= {cmd[3:0], qspi_dq};
                        nib_count <= 0;
                        state <= ST_QPI_ADDR;
                    end else begin
                        nib_count <= nib_count + 1;
                    end
                end

                ST_QPI_ADDR: begin
                    addr <= {addr[19:0], qspi_dq};
                    if (nib_count == 5) begin
                        addr <= {addr[19:0], qspi_dq};
                        nib_count <= 0;

                        if (selected_dev == DEV_FLASH) begin
                            dummy_left <= FLASH_CONT_DUMMY_NIBBLES[5:0];
                            state <= (FLASH_CONT_DUMMY_NIBBLES == 0) ? ST_QPI_RDATA : ST_QPI_DUMMY;
                        end else if (cmd == 8'h02 || cmd == 8'h38) begin
                            state <= ST_QPI_WDATA;
                        end else if (cmd == 8'h0B || cmd == 8'hEB) begin
                            dummy_left <= PSRAM_QPI_DUMMY_NIBBLES[5:0];
                            state <= (PSRAM_QPI_DUMMY_NIBBLES == 0) ? ST_QPI_RDATA : ST_QPI_DUMMY;
                        end else if (cmd == 8'hF5) begin
                            if (selected_dev == DEV_RAMA) ram_a_qpi_mode <= 1'b0;
                            if (selected_dev == DEV_RAMB) ram_b_qpi_mode <= 1'b0;
                            state <= ST_IDLE;
                        end else begin
                            state <= ST_IDLE;
                        end
                    end else begin
                        nib_count <= nib_count + 1;
                    end
                end

                ST_QPI_DUMMY: begin
                    if (dummy_left <= 1) begin
                        dummy_left <= 0;
                        state <= ST_QPI_RDATA;
                    end else begin
                        dummy_left <= dummy_left - 1;
                    end
                end

                ST_QPI_WDATA: begin
                    if (!low_nibble_phase) begin
                        byte_buf[7:4] <= qspi_dq;
                        low_nibble_phase <= 1'b1;
                    end else begin
                        byte_buf[3:0] <= qspi_dq;
                        mem_write_byte(selected_dev, addr, {byte_buf[7:4], qspi_dq});
                        addr <= addr + 1;
                        low_nibble_phase <= 1'b0;
                    end
                end

                ST_SPI_CMD: begin
                    cmd <= {cmd[6:0], qspi_dq[0]};
                    if (bit_count == 7) begin
                        cmd <= {cmd[6:0], qspi_dq[0]};
                        bit_count <= 0;

                        case ({cmd[6:0], qspi_dq[0]})
                            8'hFF: begin
                                if (selected_dev == DEV_FLASH) flash_continuous_mode <= 1'b0;
                                state <= ST_IDLE;
                            end

                            8'hAB: begin
                                state <= ST_IDLE;
                            end

                            8'h06: begin
                                if (selected_dev == DEV_FLASH) flash_write_enable <= 1'b1;
                                state <= ST_IDLE;
                            end

                            8'h04: begin
                                if (selected_dev == DEV_FLASH) flash_write_enable <= 1'b0;
                                state <= ST_IDLE;
                            end

                            8'h35: begin
                                if (selected_dev == DEV_RAMA) ram_a_qpi_mode <= 1'b1;
                                if (selected_dev == DEV_RAMB) ram_b_qpi_mode <= 1'b1;
                                state <= ST_IDLE;
                            end

                            8'hF5: begin
                                if (selected_dev == DEV_RAMA) ram_a_qpi_mode <= 1'b0;
                                if (selected_dev == DEV_RAMB) ram_b_qpi_mode <= 1'b0;
                                state <= ST_IDLE;
                            end

                            8'h05: begin
                                id_buf <= {6'b0, 1'b0, flash_write_enable}; // SR1 WEL bit approximated
                                state <= ST_SPI_STATUS;
                            end

                            8'h9F: begin
                                id_index <= 0;
                                state <= ST_SPI_ID;
                            end

                            8'h90, 8'h03, 8'h0B, 8'h02, 8'h20, 8'hEB: begin
                                state <= ST_SPI_ADDR;
                            end

                            default: begin
                                state <= ST_IDLE;
                            end
                        endcase
                    end else begin
                        bit_count <= bit_count + 1;
                    end
                end

                ST_SPI_ADDR: begin
                    addr <= {addr[22:0], qspi_dq[0]};
                    if (bit_count == 23) begin
                        addr <= {addr[22:0], qspi_dq[0]};
                        bit_count <= 0;

                        if (cmd == 8'h20 && selected_dev == DEV_FLASH) begin
                            erase_flash_sector_4k({addr[22:0], qspi_dq[0]});
                            state <= ST_IDLE;
                        end else if (cmd == 8'h02) begin
                            state <= ST_SPI_WDATA;
                        end else if (cmd == 8'h0B || cmd == 8'hEB) begin
                            if (cmd == 8'hEB && selected_dev == DEV_FLASH) flash_continuous_mode <= 1'b1;
                            dummy_left <= 8; // one byte-ish dummy for SPI init/probe path
                            state <= ST_SPI_DUMMY;
                        end else begin
                            state <= ST_SPI_RDATA;
                        end
                    end else begin
                        bit_count <= bit_count + 1;
                    end
                end

                ST_SPI_DUMMY: begin
                    if (dummy_left <= 1) begin
                        dummy_left <= 0;
                        state <= ST_SPI_RDATA;
                    end else begin
                        dummy_left <= dummy_left - 1;
                    end
                end

                ST_SPI_WDATA: begin
                    byte_buf <= {byte_buf[6:0], qspi_dq[0]};
                    if (bit_count == 7) begin
                        mem_write_byte(selected_dev, addr, {byte_buf[6:0], qspi_dq[0]});
                        addr <= addr + 1;
                        bit_count <= 0;
                    end else begin
                        bit_count <= bit_count + 1;
                    end
                end

                default: ;
            endcase
        end
    end

    // Output side: drive read data after falling SCK, so the master can sample on next rising SCK.
    always @(negedge qspi_sck) begin
        if (selected_dev != DEV_NONE) begin
            case (state)
                ST_QPI_RDATA: begin
                    dq_oe <= 1'b1;
                    if (!low_nibble_phase) begin
                        byte_buf = mem_read_byte(selected_dev, addr);
                        dq_out <= byte_buf[7:4];
                        low_nibble_phase <= 1'b1;
                    end else begin
                        dq_out <= byte_buf[3:0];
                        low_nibble_phase <= 1'b0;
                        addr <= addr + 1;
                    end
                end

                ST_SPI_RDATA: begin
                    dq_oe <= 1'b1;
                    if (bit_count == 0) byte_buf = mem_read_byte(selected_dev, addr);
                    dq_out <= {2'bzz, byte_buf[7 - bit_count], 1'bz}; // IO1/MISO
                    if (bit_count == 7) begin
                        bit_count <= 0;
                        addr <= addr + 1;
                    end else begin
                        bit_count <= bit_count + 1;
                    end
                end

                ST_SPI_STATUS: begin
                    dq_oe <= 1'b1;
                    dq_out <= {2'bzz, id_buf[7 - bit_count], 1'bz};
                    if (bit_count == 7) bit_count <= 0;
                    else bit_count <= bit_count + 1;
                end

                ST_SPI_ID: begin
                    dq_oe <= 1'b1;
                    case (selected_dev)
                        DEV_FLASH: begin
                            case (id_index)
                                0: id_buf = 8'hEF; // Winbond-like manufacturer
                                1: id_buf = 8'h40;
                                2: id_buf = 8'h18;
                                default: id_buf = 8'h00;
                            endcase
                        end
                        DEV_RAMA, DEV_RAMB: begin
                            case (id_index)
                                0: id_buf = 8'h0D; // AP Memory-like placeholder
                                1: id_buf = 8'h5D;
                                default: id_buf = 8'h00;
                            endcase
                        end
                        default: id_buf = 8'h00;
                    endcase

                    dq_out <= {2'bzz, id_buf[7 - bit_count], 1'bz};
                    if (bit_count == 7) begin
                        bit_count <= 0;
                        id_index <= id_index + 1;
                    end else begin
                        bit_count <= bit_count + 1;
                    end
                end

                default: begin
                    if (state != ST_QPI_RDATA && state != ST_SPI_RDATA && state != ST_SPI_ID && state != ST_SPI_STATUS) begin
                        dq_oe <= 1'b0;
                        dq_out <= 4'h0;
                    end
                end
            endcase
        end else begin
            dq_oe <= 1'b0;
            dq_out <= 4'h0;
        end
    end

endmodule
