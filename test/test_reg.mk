# Makefile

# defaults
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

SRC = $(PWD)/../src
VERILOG_SOURCES += $(SRC)/register_file.v
COMPILE_ARGS += -DSIM

# toplevel verilog file
TOPLEVEL = register_file

# name of python file
MODULE = test_registers

include $(shell cocotb-config --makefiles)/Makefile.sim