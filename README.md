# Core Logical Structure

In a behavioural sense, `src/core.v` follows this block diagram:

> [!NOTE]
> `src/core.v` is actually implemented using a multi-cycle, state-externalized structure. The next two sections detail this structure. This block diagram is the logical view from which this core was developed.

![CPU Block Diagram](images/single-cycle-processor.png)

Image source: *Digital Design & Computer Architecture*, Chapter 7: “Microarchitecture,” by Sarah Harris and David Harris.  
https://pages.hmc.edu/harris/class/e85/DDCArv_Ch7.pdf

# Core FSM

The core stores the register file, instruction memory, and data memory on an external QSPI PMOD. The core implements a simple state machine:

![CPU State Machine](images/custom%20core-state%20diagram.png)

# Interaction with QSPI PMOD

`src/qspi_ctrl.v` provides an abstract interface for the core to obtain register data, instruction data and memory data from the external QSPI PMOD.

![Memory Control Structure](images/custom%20core-qspi%20structure.png)