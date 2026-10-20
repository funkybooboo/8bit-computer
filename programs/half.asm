; half.asm - halve x, without a shift instruction: search for it
;
; There is no right-shift, so find y with y + y = x instead: run y
; upward until doubling it hits x exactly (the SUB sets ZF). Halving
; as a search loop - a different algorithm class from the counting
; loops elsewhere here. Exactly 16 bytes.
;
; Edge case: x must be even - 2y mod 256 is always even, so an odd x
; never satisfies the test and the search runs forever.

        LDI 0
        STA y        ; y = 0 (re-runnable without re-entering the image)
loop:   LDA y
        ADD y        ; A = 2y
        SUB x        ; ZF=1 iff 2y == x
        JZ  done
        LDA y
        ADD one
        STA y        ; y += 1
        JMP loop
done:   LDA y
        OUT          ; x / 2
        HLT
x:      .DB 22       ; must be even
y:      .DB 0
one:    .DB 1
