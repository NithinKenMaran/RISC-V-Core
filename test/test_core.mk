SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TOPLEVEL = core
MODULE = test_core

SRC := $(PWD)/../src
INC := $(PWD)/../include

VERILOG_SOURCES += $(SRC)/core.v
VERILOG_SOURCES += $(SRC)/decoder.v
VERILOG_SOURCES += $(SRC)/register_file.v
VERILOG_SOURCES += $(SRC)/alu.v

# Needed for params.vh
COMPILE_ARGS += -I$(INC)

# Uncomment if/when you add `ifdef DEBUG guarded ports/signals.
# COMPILE_ARGS += -DDEBUG

# Helpful with newer syntax if you move toward SystemVerilog later.
# COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
