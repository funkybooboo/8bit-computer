; odometer.asm - count 0..99 in decimal, forever
;
; count.asm counts bytes: 0..255, a full power-of-two cycle. A human
; odometer counts 0..99 and rolls over - which needs a compare against
; 100, and the operand field only carries 0-15. The trick: SUB hundred
; compares for free (it sets ZF exactly when the count is 100), and for
; every count below 100 the wrapped subtraction comes back with
; ADD hundred (A - 100 + 256 + 100 = A). The compare never leaves a
; copy to restore - the arithmetic restores itself. Flip the display
; to decimal (DEC_HEX switch) and watch a two-digit odometer roll.

        LDI 0
loop:   OUT             ; display the count
        ADDI 1          ; count++
        SUB hundred     ; ZF=1 exactly when count == 100
        JZ reset        ; the odometer rolls over
        ADD hundred     ; count < 100: undo the wrapped subtraction
        JMP loop
reset:  LDI 0
        JMP loop

hundred: .DB 100
