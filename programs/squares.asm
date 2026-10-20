; squares.asm - square numbers from the sum-of-odds identity
;
; 1 + 3 + 5 + ... + (2n-1) = n^2, so adding successive odd numbers to
; a running sum generates the squares: the display shows 1, 4, 9, 16,
; ... 225, then wraps mod 256 (16^2 = 0, 17^2 = 33, ...).

loop:   LDA s
        ADD odd      ; s += the next odd number
        STA s
        OUT          ; n^2 (mod 256)
        LDA odd
        ADD two
        STA odd      ; odd += 2
        JMP loop
s:      .DB 0        ; the running square
odd:    .DB 1        ; 1, 3, 5, 7, ...
two:    .DB 2
