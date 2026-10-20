; div.asm - divide x by y by repeated subtraction - long division,
; visible
;
; Each lap subtracts y from x and shows the running remainder
; (91, 82, 73, ...), counting the subtractions in q; when x < y the
; quotient is complete: display 100/9 = 11, remainder 1 (left in x).
; Exactly 16 bytes - every byte of RAM is working here.

loop:   LDA x
        SUB y        ; A = x - y; CF=1 iff x >= y
        JC  take
        LDA q
        OUT          ; the quotient (the final display)
        HLT
take:   STA x        ; x -= y (A already is x - y)
        OUT          ; the running remainder
        LDA q
        ADD one
        STA q        ; q += 1
        JMP loop
x:      .DB 100      ; dividend
y:      .DB 9        ; divisor
q:      .DB 0        ; quotient
one:    .DB 1
