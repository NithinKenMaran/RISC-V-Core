# Compiler
IVERILOG = iverilog
VVP = vvp

# Flags
FLAGS = -g2012 -I tb -I src

# Files
SRC = src/*.v
TB = tb/tb.v

# Output
OUT = sim

# Default target
all: run

compile:
	$(IVERILOG) $(FLAGS) -o $(OUT) $(TB) $(SRC)

run: compile
	$(VVP) $(OUT)

wave: run
	gtkwave wave.vcd

clean:
	rm -f $(OUT) wave.vcd
