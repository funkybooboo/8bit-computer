; step.asm - count by 3 through every byte value
;
; ADDI adds a constant straight from the instruction - no RAM cell holds
; the step, unlike count.asm which adds M[one]. Any odd step (3, 5, 7,
; ... 15) is coprime with 256, so the display walks through all 256
; byte values before repeating; an even step would only visit half of
; them. Change one nibble and the step changes.

loop:   OUT
        ADDI 3
        JMP loop
