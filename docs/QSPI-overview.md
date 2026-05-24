# QSPI Overview

## Architecture

The core never drives the QSPI bus directly. All QSPI signalling is handled by `qspi_ctrl`, which sits between the core and the physical pins.

```
core.v  <--req/resp-->  qspi_ctrl.v  <--SCK/CS/DQ-->  QSPI PMOD
```

There are two separate conversations:

- **core ↔ qspi_ctrl**: a simple request/response handshake over internal wires
- **qspi_ctrl ↔ PMOD**: nibble-level QSPI signalling on the physical bus

---

## The Internal Interface (core ↔ qspi_ctrl)

The core issues a request by holding these signals:

```
qspi_req_valid  = 1       — request is pending
qspi_req_target           — FLASH (CS0), REGS/RAM A (CS1), DMEM/RAM B (CS2)
qspi_req_write            — 0 for read, 1 for write
qspi_req_addr             — 32-bit byte address
qspi_req_wdata            — 32-bit write data (ignored for reads)
```

`qspi_ctrl` asserts `req_ready = 1` whenever it is idle. The request is accepted on the cycle where both `req_valid` and `req_ready` are high. The core then clears `req_valid` and waits.

When the QSPI transaction completes, `qspi_ctrl` pulses `resp_valid` for one cycle. For reads, `resp_rdata` carries the 32-bit result. For writes, `resp_rdata` is zero.

---

## Device and CS Mapping

| Target | Device | CS line | Used for |
|---|---|---|---|
| `TARGET_FLASH` | NOR flash | CS0 | Instruction fetch |
| `TARGET_REGS` | PSRAM A | CS1 | Register file reads and writes |
| `TARGET_DMEM` | PSRAM B | CS2 | Data memory reads and writes |

Register addresses are word-aligned: register `x1` is at byte address `1*4 = 4`, `x2` at `8`, and so on.

---

## Scenario 1: Instruction Fetch (Flash Read)

The core is in `S_FETCH_REQ`. It sets `req_target = TARGET_FLASH`, `req_write = 0`, `req_addr = pc`.

**qspi_ctrl asserts CS0 low and sends three segments:**

1. **SEND 6 nibbles** — drives `pc[23:0]` onto `qspi_dq[3:0]`, high nibble first. The PMOD (already in flash continuous mode) is in `ST_QPI_ADDR`, shifting each nibble into its `addr` register on each posedge SCK.

2. **DUMMY 6 nibbles** — releases the bus (`dq_oe = 0`) and clocks 6 cycles. The PMOD counts these down in `ST_QPI_DUMMY`.

3. **READ 8 nibbles** — releases the bus and samples `qspi_dq[3:0]` on each posedge SCK, shifting into `read_shift`. The PMOD is in `ST_QPI_RDATA`, driving one nibble per negedge SCK from `flash[addr]`, high nibble of each byte first.

**qspi_ctrl asserts CS0 high**, sets `resp_rdata = read_shift`, and pulses `resp_valid`.

The core in `S_FETCH_WAIT` latches `resp_rdata` into `instr_reg` and moves to `S_DECODE`.

---

## Scenario 2: Register Read (PSRAM A Read)

The core is in `S_RS1_REQ` or `S_RS2_REQ`. It sets `req_target = TARGET_REGS`, `req_write = 0`, `req_addr = rs1 * 4` (or `rs2 * 4`).

**qspi_ctrl asserts CS1 low and sends four segments:**

1. **SEND 2 nibbles** — drives the read command `0xEB` in QPI (high nibble `0xE`, then low nibble `0xB`). The PMOD is in `ST_QPI_CMD`, assembling the command byte from two nibbles on posedge SCK.

2. **SEND 6 nibbles** — drives the 24-bit register address, high nibble first. The PMOD moves to `ST_QPI_ADDR` and shifts in the address.

3. **DUMMY 6 nibbles** — releases the bus and clocks 6 dummy cycles. The PMOD counts these down in `ST_QPI_DUMMY`.

4. **READ 8 nibbles** — releases the bus and samples `qspi_dq[3:0]` on each posedge SCK. The PMOD is in `ST_QPI_RDATA`, driving `ram_a[addr]` nibble by nibble.

**qspi_ctrl asserts CS1 high**, sets `resp_rdata = read_shift`, and pulses `resp_valid`.

The core latches `resp_rdata` into `rs1_data` (or `rs2_data`) and moves on.

---

## Scenario 3: Register Write (PSRAM A Write)

The core is in `S_WB_REQ`. It sets `req_target = TARGET_REGS`, `req_write = 1`, `req_addr = rd * 4`, `req_wdata = wb_data`.

**qspi_ctrl asserts CS1 low and sends three segments:**

1. **SEND 2 nibbles** — drives the write command `0x38` in QPI.

2. **SEND 6 nibbles** — drives the 24-bit register address, high nibble first. The PMOD moves through `ST_QPI_CMD` and `ST_QPI_ADDR`.

3. **SEND 8 nibbles** — drives `wb_data[31:0]`, high nibble first. The PMOD is in `ST_QPI_WDATA`, collecting nibble pairs and writing each completed byte to `ram_a[addr]` immediately.

There is no dummy phase for writes.

**qspi_ctrl asserts CS1 high** and pulses `resp_valid` (with `resp_rdata = 0`).

The core in `S_WB_WAIT` sees `resp_valid` and moves to `S_PC_UPDATE`.

---

## Scenario 4: Data Memory Read (PSRAM B Read)

The core is in `S_MEM_REQ` executing a load instruction. It sets `req_target = TARGET_DMEM`, `req_write = 0`, `req_addr = alu_result_reg` (the computed address).

Identical protocol to Scenario 2, but **qspi_ctrl uses CS2** (PSRAM B) instead of CS1. The PMOD model reads from `ram_b[]` in `ST_QPI_RDATA`.

**qspi_ctrl asserts CS2 high**, pulses `resp_valid` with the 32-bit loaded value.

The core latches `resp_rdata` into `mem_rdata_reg` and moves to `S_WB_REQ`.

---

## Scenario 5: Data Memory Write (PSRAM B Write)

The core is in `S_MEM_REQ` executing a store instruction. It sets `req_target = TARGET_DMEM`, `req_write = 1`, `req_addr = alu_result_reg`, `req_wdata = rs2_data`.

Identical protocol to Scenario 3, but **qspi_ctrl uses CS2** (PSRAM B). The PMOD writes each byte into `ram_b[]` in `ST_QPI_WDATA`.

**qspi_ctrl asserts CS2 high** and pulses `resp_valid`.

The core moves to `S_WB_REQ` (no writeback for a store, so `S_WB_REQ` skips to `S_PC_UPDATE`).

---

## Transaction Cycle Count

Each QSPI transaction costs the same number of QSPI clock cycles regardless of which device is targeted, because the dummy counts match:

| Transaction | QSPI nibble cycles |
|---|---|
| Flash read (addr + dummy + 4 bytes) | 6 + 6 + 8 = 20 |
| PSRAM read (cmd + addr + dummy + 4 bytes) | 2 + 6 + 6 + 8 = 22 |
| PSRAM write (cmd + addr + 4 bytes) | 2 + 6 + 8 = 16 |

Each QSPI nibble cycle is two core clock cycles (one for SCK low, one for SCK high). One instruction with `add x3, x1, x2` therefore takes: 1 flash read + 2 register reads + 1 register write = 20 + 22 + 22 + 16 = 80 QSPI nibble cycles = 160 core clock cycles, plus FSM overhead.
