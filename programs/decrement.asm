; decrement.asm - countdown with no data cell
;
; countdown.asm needs a RAM cell holding 1 to subtract; SUBI takes the
; constant straight from the instruction, so the whole program is code.
; This is the classic decrement-and-test loop: OUT, subtract, test,
; branch. Displays 10 down to 0 - the JZ exit catches the exact zero,
; and "done" gets one more OUT to display it.

        LDI 10
loop:   OUT
        SUBI one        ; A = A - 1; ZF=1 when A hits 0
        JZ done
        JMP loop
done:   OUT             ; show the final 0
        HLT

one:    .EQU 1          ; the decrement, as a named constant
