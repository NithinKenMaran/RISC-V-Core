# Test Core
```bash
make -f test_core.mk
```

## Core Test Output
```
 178.01ns INFO     cocotb.regression                  ****************************************************************************************
                                                        ** TEST                            STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
                                                        ****************************************************************************************
                                                        ** test_core.test_add               PASS           9.00           0.00       9890.73  **
                                                        ** test_core.test_sub               PASS          13.00           0.00      41785.55  **
                                                        ** test_core.test_sll               PASS          13.00           0.00      38783.89  **
                                                        ** test_core.test_slt_true          PASS          13.00           0.00      47500.13  **
                                                        ** test_core.test_slt_false         PASS          13.00           0.00      48001.89  **
                                                        ** test_core.test_slt_negative      PASS          13.00           0.00      48299.51  **
                                                        ** test_core.test_sltu_true         PASS          13.00           0.00      49037.90  **
                                                        ** test_core.test_sltu_false        PASS          13.00           0.00      49393.25  **
                                                        ** test_core.test_sltu_unsigned     PASS          13.00           0.00      49259.39  **
                                                        ** test_core.test_xor               PASS          13.00           0.00      48001.89  **
                                                        ** test_core.test_srl               PASS          13.00           0.00      48862.14  **
                                                        ** test_core.test_sra               PASS          13.00           0.00      48342.33  **
                                                        ** test_core.test_or                PASS          13.00           0.00      49617.97  **
                                                        ** test_core.test_and               PASS          13.00           0.00      48862.14  **
                                                        ****************************************************************************************
                                                        ** TESTS=14 PASS=14 FAIL=0 SKIP=0                178.01           0.06       3107.29  **
                                                        ****************************************************************************************
```

# Test R Type and I type instructions
```bash
make -f test_instr.mk clean
make -f test_instr.mk
```

# Branch test 
```bash
make -f test_branch.mk
```

## Branch Output
```
   194.01ns INFO     cocotb.regression                  **************************************************************************************
                                                        ** TEST                          STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
                                                        **************************************************************************************
                                                        ** test_branch.test_beq           PASS          29.00           0.00      25511.54  **
                                                        ** test_branch.test_bne           PASS          33.00           0.00      56404.33  **
                                                        ** test_branch.test_blt           PASS          33.00           0.00      58526.95  **
                                                        ** test_branch.test_bge           PASS          33.00           0.00      59791.03  **
                                                        ** test_branch.test_bltu          PASS          33.00           0.00      60207.14  **
                                                        ** test_branch.test_bgeu          PASS          33.00           0.00      60259.57  **
                                                        **************************************************************************************
                                                        ** TESTS=6 PASS=6 FAIL=0 SKIP=0                194.01           0.06       3063.66  **
                                                        **************************************************************************************

```
# Jump Test
```bash
make -f test_jal.mk
```

## Jump Output
```

                                                         Program layout:
                                                            0: addi x1, x0, 10
                                                            1: jal  x5, +8        -> jump to instruction 3, x5 = PC+4 = 8
                                                            2: addi x2, x0, 99    -> skipskip
                                                            3: addi x2, x0, 88    -> execute
    17.00ns INFO     cocotb.regression                  test_jal passed
    17.00ns INFO     cocotb.regression                  **************************************************************************************
                                                        ** TEST                          STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
                                                        **************************************************************************************
                                                        ** test_jal.test_jal              PASS          17.00           0.00      19117.26  **
                                                        **************************************************************************************
                                                        ** TESTS=1 PASS=1 FAIL=0 SKIP=0                 17.00           0.06        261.91  **
                                                        **************************************************************************************
```

# `jalr` (Jump & Link Register) Test

```bash
make -f test_jalr.mk
```

## `jalr` Test Output

```

                                                          Program layout:
                                                            0: addi x1, x0, base
                                                            1: jalr x5, x1, imm
                                                            2: addi x2, x0, 99   #skipskip
                                                            3: addi x2, x0, 88   #execute
x1 = 13
PC before jalr: 4
x5 after jalr: 8
PC after jalr: 12
x2 = 88
    17.00ns INFO     cocotb.regression                  test_jalr passed
    17.00ns INFO     cocotb.regression                  **************************************************************************************
                                                        ** TEST                          STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
                                                        **************************************************************************************
                                                        ** test_jalr.test_jalr            PASS          17.00           0.00      15678.84  **
                                                        **************************************************************************************
                                                        ** TESTS=1 PASS=1 FAIL=0 SKIP=0                 17.00           0.05        329.98  **
                                                        **************************************************************************************
```
