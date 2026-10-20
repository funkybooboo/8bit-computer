; powers.asm - powers of two, stopped by a flag
;
; DBL doubles A in one instruction: A <- 2*A, with CF catching the bit
; shifted out - a shift-left built from add-A-to-itself (DBL is T2
; B <- A, T3 A <- A + B). Doubling 128 wraps to 0 and sets ZF, so JNZ
; ends the run on exactly the wrap: the program stops itself without
; any comparison or counter. Displays 1, 2, 4, 8, 16, 32, 64, 128.

        LDI 1
loop:   OUT
        DBL             ; A = 2*A; ZF=1 when it wrapped to 0
        JNZ loop
        HLT
