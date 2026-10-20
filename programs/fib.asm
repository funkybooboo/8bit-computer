; fib.asm - Fibonacci numbers, mod 256, forever
;
; Ben Eater's classic demo program. Each round: x, y = y, x + y, and
; the smaller (x) is displayed. The three .DB bytes are the initial
; state - they are entered into RAM together with the code - and the
; sequence wraps mod 256 once the sums pass 255 (233 + 144 = 121).

loop:   LDA x        ; A = x (the smaller)
        OUT          ; display it
        ADD y        ; A = x + y
        STA t        ; t = x + y
        LDA y
        STA x        ; x = y
        LDA t
        STA y        ; y = old x + y
        JMP loop
x:      .DB 0        ; initial pair: 0, 1
y:      .DB 1
t:      .DB 0
