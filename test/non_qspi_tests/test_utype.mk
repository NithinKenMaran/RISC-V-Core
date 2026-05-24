SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TOPLEVEL = core
MODULE = test_utype

SRC := $(PWD)/../src
INC := $(PWD)/../include

VERILOG_SOURCES += $(SRC)/core.v
VERILOG_SOURCES += $(SRC)/decoder.v
VERILOG_SOURCES += $(SRC)/register_file.v
VERILOG_SOURCES += $(SRC)/alu.v
VERILOG_SOURCES += $(SRC)/extender.v
VERILOG_SOURCES += $(SRC)/control_unit.v

COMPILE_ARGS += -I$(INC)

# COMPILE_ARGS += -DDEBUG
# COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim