; mul.asm - multiply x by y (repeated addition), showing every partial
; product - the times table for x
;
; There is no multiply: the loop IS multiplication - r += x, y laps.
; OUT after each STA shows the running product, so the display walks
; the times-table row for x: with x=7, y=6 it shows 7, 14, 21, 28,
; 35, 42, then halts. The exit test sits right after the SUB that
; sets ZF (flags only change on ADD/SUB, so every JZ reads a fresh
; result).
;
; Edge case: y=0 does not exit immediately - it runs 256 laps and the
; display ends at 0, which is still the right answer, because
; x*0 and x*256 are the same byte (mod 256). The wrap fixes it.

loop:   LDA r
        ADD x        ; r += x
        STA r        ; (A still holds r)
        OUT          ; the partial product
        LDA y
        SUB one      ; y -= 1; ZF fresh from this SUB
        STA y
        JZ  done     ; the y-th lap is finished
        JMP loop
done:   HLT          ; the display already shows x*y
r:      .DB 0        ; the product
x:      .DB 7        ; multiplicand
y:      .DB 6        ; multiplier (laps; 0 works, see above)
one:    .DB 1
