; absdiff.asm - the absolute difference |x - y|
;
; The textbook use of a borrow flag: SUB x sets CF=1 when A >= x (no
; borrow - the comparison rule every program on this machine leans on,
; instruction-set.md "SUB"), so the same subtraction both computes the
; difference and picks its direction. x >= y: the difference is already
; in A. x < y: the wrapped subtraction is thrown away and y - x is
; computed instead - two subtractions, one answer, no flags re-tested.
; With x = 9 and y = 14 the display shows |9 - 14| = 5; swap the data
; bytes and it shows 5 again.

        LDA x
        SUB y           ; CF=1 iff x >= y; A = x - y when it is
        JC done         ; x >= y: the difference is already in A
        LDA y           ; x < y: |x - y| = y - x
        SUB x
done:   OUT
        HLT

x:      .DB 9
y:      .DB 14
