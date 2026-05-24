`timescale 1ns/1ps

// Simulation-only top for QSPI-integrated core tests.
//
// Phase A:
//   cocotb drives host_* signals while host_active=1, emulating the
//   TinyTapeout PCB/RP2040 owning the QSPI PMOD pins before handoff.
//
// Phase B:
//   host_active=0. The core owns qspi_sck/qspi_cs_n/qspi_dq and talks to
//   the same qspi_pmod model.

module top_qspi_tb;
    reg clk;
    reg reset;

    wire       core_qspi_sck;
    wire [2:0] core_qspi_cs_n;
    wire [3:0] qspi_dq_bus;

    // RP2040-like temporary host bus master for Phase A.
    reg        host_active;
    reg        host_sck;
    reg [2:0]  host_cs_n;
    reg [3:0]  host_dq_out;
    reg        host_dq_oe;
    wire [3:0] host_dq_in;

    wire       pmod_sck;
    wire [2:0] pmod_cs_n;

    assign pmod_sck  = host_active ? host_sck  : core_qspi_sck;
    assign pmod_cs_n = host_active ? host_cs_n : core_qspi_cs_n;

    // During Phase A the core is held in reset, so its qspi_dq should be Z.
    // During Phase B host_dq_oe=0 and host_active=0, so the host releases the bus.
    assign qspi_dq_bus = (host_active && host_dq_oe) ? host_dq_out : 4'bzzzz;
    assign host_dq_in  = qspi_dq_bus;

    core dut (
        .clk(clk),
        .reset(reset),
        .qspi_sck(core_qspi_sck),
        .qspi_cs_n(core_qspi_cs_n),
        .qspi_dq(qspi_dq_bus)
    );

    qspi_pmod pmod (
        .qspi_sck(pmod_sck),
        .qspi_cs_n(pmod_cs_n),
        .qspi_dq(qspi_dq_bus)
    );

    initial begin
        clk = 1'b0;
        reset = 1'b1;

        host_active = 1'b1;
        host_sck    = 1'b0;
        host_cs_n   = 3'b111;
        host_dq_out = 4'h0;
        host_dq_oe  = 1'b0;
    end
endmodule
