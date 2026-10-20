; count.asm - count 0..255 forever, displaying each value
;
; The ALU is 8-bit and wraps naturally (255 + 1 = 0), so no conditional
; is needed: this counts 0, 1, 2, ..., 255, 0, 1, ... forever.
;
; There is no increment instruction, so the +1 is a data byte read by ADD
; (ADD can only take a RAM address, not an immediate).

        LDI 0        ; A = 0 (the counter)
loop:   OUT          ; display A
        ADD one      ; A = A + 1 (wraps 255 -> 0)
        JMP loop
one:    .DB 1        ; the constant +1
