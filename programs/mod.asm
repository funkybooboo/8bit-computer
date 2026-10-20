; mod.asm - display x mod y (the remainder)
;
; The stripped core of div.asm: subtract y until x < y - what is left
; in x IS the remainder. 9 bytes, the smallest arithmetic loop here.
; With 100 mod 9 the display ends at 1.

loop:   LDA x
        SUB y        ; CF=1 iff x >= y
        JC  take
        LDA x
        OUT          ; x < y: the remainder
        HLT
take:   STA x        ; x -= y
        JMP loop
x:      .DB 100
y:      .DB 9
