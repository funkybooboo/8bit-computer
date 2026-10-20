; rol.asm - rotate A left through carry, forever
;
; rotate.asm (5 instructions + a data cell) builds the same trick out of
; ADD self + JC + ADD one. DBL is the shift (CF = bit shifted out), JNC
; skips the fixup when nothing wrapped, ADDI 1 rotates the carried bit
; back into bit 0. No data cell, and the seed never has to sit in RAM:
; any value in A rotates. Displays a bit pattern circling a byte,
; taking exactly 8 steps per revolution (256 per 32 patterns - every
; byte value passes through A before the cycle repeats).

        LDI 0b1011       ; the seed pattern
loop:   DBL             ; A = 2*A, CF = bit shifted out
        JNC shown       ; nothing carried: pattern just moved left
        ADDI 1          ; carry the bit around into bit 0
shown:  OUT
        JMP loop
