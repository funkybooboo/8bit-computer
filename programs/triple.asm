; triple.asm - powers of three, by shift-and-add
;
; Multiplying by three is (x << 1) + x - the strength reduction every
; compiler makes when a constant multiply is cheaper than a multiply
; instruction. DBL is the shift, ADD x is the add, and the RAM cell x is
; the multiplicand both of them read. The whole program is a 5-instruction
; loop; no counter and no comparison - powers.asm is the same shape with
; the add dropped. Displays the powers of three mod 256: 3, 9, 27, 81,
; 243, 217, ... - never zero, and back to 1 after 64 laps (3 is a unit
; mod 256, so the sequence cycles instead of collapsing).

        LDA x
loop:   DBL             ; A = 2*x
        ADD x           ; A = 2*x + x = 3*x
        STA x
        OUT
        JMP loop

x:      .DB 1
