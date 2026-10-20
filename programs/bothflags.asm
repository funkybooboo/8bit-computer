; bothflags.asm - one ADD setting both flags at once: 255 + 1
;
; The full adder carries out (CF=1) and the result is zero (ZF=1) in
; the same instruction - the only byte whose successor is exactly 0
; with a carry. Both conditional jumps are shown testing the same
; operation: JC takes it, and so would JZ.

        LDI 15
        ADD m240     ; A = 15 + 240 = 255, the largest byte
        OUT          ; 255
        ADD one      ; 255 + 1: CF=1 AND ZF=1 together
        JC  done     ; taken - the carry wrapped the byte
        JZ  done     ; also taken - the result is zero
done:   OUT          ; 0
        HLT
m240:   .DB 240
one:    .DB 1
