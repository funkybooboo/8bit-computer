; min.asm - display min(x, 10): a guard against a threshold
;
; SUBI compares A against a constant without a RAM cell for it - the
; machine could not previously test against anything it was not willing
; to store. SUBI limit sets CF=1 when A >= limit, so JNC means "strictly
; below the limit". The compare clobbers A, so both branches re-load;
; with x = 25 the display shows 10. Edit x (address 9) to 7 and re-enter
; the program to take the other branch and show 7. Change `limit` and the
; whole program follows - that is what .EQU is for.

limit:  .EQU 10          ; the threshold, as a named constant

        LDA x           ; A = x
        SUBI limit      ; CF=1 iff x >= limit (A becomes x-limit, discarded)
        JNC small       ; x < limit: keep x
        LDI limit       ; x >= limit: clamp to the limit
        OUT
        HLT
small:  LDA x
        OUT
        HLT
x:      .DB 25
