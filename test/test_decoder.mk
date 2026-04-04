# Makefile

# defaults
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

SRC = $(PWD)/../src
VERILOG_SOURCES += $(SRC)/decoder.v
COMPILE_ARGS += -DSIM

# include params.vh
INC = $(PWD)/../include
COMPILE_ARGS += -I$(INC)

# toplevel verilog file
TOPLEVEL = decoder

# name of python file
MODULE = test_decoder

include $(shell cocotb-config --makefiles)/Makefile.sim