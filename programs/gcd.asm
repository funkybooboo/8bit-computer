; gcd.asm - Euclid's algorithm: the greatest common divisor of x and y
;
; The oldest algorithm still in daily use (it reduces fractions:
; gcd(252, 105) = 21, so 252/105 = 12/5). Subtractive Euclid: while
; x != y, subtract the smaller from the larger; the equal value is
; the answer. One SUB does triple duty: A = x - y, ZF tests x == y,
; CF tests x >= y.

loop:   LDA x
        SUB y        ; ZF=1 iff x == y; CF=1 iff x >= y
        JZ  done
        JC  take
        LDA y        ; y > x: y -= x
        SUB x
        STA y
        JMP loop
take:   STA x        ; x >= y: x -= y (A already is x - y)
        JMP loop
done:   LDA x
        OUT          ; x == y: the gcd
        HLT
x:      .DB 252
y:      .DB 105
