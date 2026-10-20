; larger.asm - display the larger of two data bytes
;
; SUB sets CF=1 when there is no borrow, i.e. when A >= B, so JC acts
; as "jump if greater or equal" - a comparison without a compare
; instruction. SUB clobbers A (it becomes x - y), so the winner is
; re-loaded from RAM. Change the two data bytes and re-enter to take
; the other branch.

        LDA x        ; A = x
        SUB y        ; CF=1 iff x >= y; A = x - y (discarded)
        JC  xwins
        LDA y        ; y > x
        OUT
        HLT
xwins:  LDA x        ; x >= y
        OUT
        HLT
x:      .DB 9
y:      .DB 14
