; lcg.asm - a full-period pseudorandom sequence: x = 5x + 1 (mod 256)
;
; A linear congruential generator built from four ADDs. By the
; Hull-Dobell theorem (a=5 is 1 mod 4, c=1 is odd, m=256) it has full
; period: the 256 outputs are a permutation of every byte 0..255,
; then repeat. Watch it shuffle on the display - the closest thing to
; randomness this machine can make (no XOR, so no LFSR).

loop:   LDA s
        ADD s
        ADD s
        ADD s
        ADD s        ; A = 5s
        ADD one      ; A = 5s + 1
        STA s
        OUT
        JMP loop
s:      .DB 1        ; the seed (any value: all seeds give the same cycle)
one:    .DB 1
