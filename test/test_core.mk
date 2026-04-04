# Makefile

# defaults
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

SRC = $(PWD)/../src
VERILOG_SOURCES += $(SRC)/core.v
COMPILE_ARGS += -DSIM

# include params.vh
INC = $(PWD)/../include
COMPILE_ARGS += -I$(INC)

# toplevel verilog file
TOPLEVEL = core 

# name of python file
MODULE = test_core 

include $(shell cocotb-config --makefiles)/Makefile.sim