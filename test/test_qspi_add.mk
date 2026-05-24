SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TOPLEVEL = top_qspi_tb
MODULE = test_qspi_add

.DEFAULT_GOAL := sim

SRC := $(PWD)/../src
INC := $(PWD)/../include

MEM_DIR := $(PWD)/mem
FLASH_HEX := $(MEM_DIR)/flash.hex
RAMA_HEX  := $(MEM_DIR)/rama.hex
RAMB_HEX  := $(MEM_DIR)/ramb.hex

prepare_mem:
	mkdir -p $(MEM_DIR)
	cd $(PWD) && python3 -c "\
import sys; sys.path.insert(0,'include'); \
from mem_image import MemoryImage, reg_addr; \
from riscv_encode import encode_add, encode_nop; \
flash=MemoryImage(); rama=MemoryImage(); ramb=MemoryImage(); \
flash.set_word_qspi(0x0000,encode_add(rd=3,rs1=1,rs2=2)); \
flash.set_word_qspi(0x0004,encode_nop()); \
flash.set_word_qspi(0x0008,encode_nop()); \
rama.set_word_qspi(reg_addr(1),10); \
rama.set_word_qspi(reg_addr(2),20); \
rama.set_word_qspi(reg_addr(3),0xDEADBEEF); \
flash.write_hex('$(FLASH_HEX)'); \
rama.write_hex('$(RAMA_HEX)'); \
ramb.write_hex('$(RAMB_HEX)') \
"

VERILOG_SOURCES += $(PWD)/top_qspi_tb.v
VERILOG_SOURCES += $(PWD)/qspi_pmod.v
VERILOG_SOURCES += $(SRC)/core.v
VERILOG_SOURCES += $(SRC)/qspi_ctrl.v
VERILOG_SOURCES += $(SRC)/alu.v
VERILOG_SOURCES += $(SRC)/control_unit.v
VERILOG_SOURCES += $(SRC)/decoder.v
VERILOG_SOURCES += $(SRC)/extender.v

COMPILE_ARGS += -g2012
COMPILE_ARGS += -I$(INC)


sim: prepare_mem
results.xml: prepare_mem

include $(shell cocotb-config --makefiles)/Makefile.sim