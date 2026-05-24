SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TOPLEVEL = top_qspi_tb
MODULE = test_core_extensive

.DEFAULT_GOAL := sim

SRC := $(PWD)/../src
INC := $(PWD)/../include

MEM_DIR := $(PWD)/mem
FLASH_HEX := $(MEM_DIR)/flash.hex
RAMA_HEX  := $(MEM_DIR)/rama.hex
RAMB_HEX  := $(MEM_DIR)/ramb.hex

# Create zeroed placeholder hex files so qspi_pmod's initial $readmemh
# doesn't fail on startup. Each test overwrites these via load_images_into_pmod.
prepare_mem:
	mkdir -p $(MEM_DIR)
	cd $(PWD) && python3 -c "\
import sys; sys.path.insert(0,'include'); \
from mem_image import MemoryImage; \
MemoryImage().write_hex('$(FLASH_HEX)'); \
MemoryImage().write_hex('$(RAMA_HEX)'); \
MemoryImage().write_hex('$(RAMB_HEX)') \
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
