; memory.asm - a RAM byte as a loop variable (read-modify-write)
;
; The same count-up as count.asm, but the counter lives in RAM instead
; of the A register: LDA loads it, ADD bumps it, STA stores it back.
; That read-modify-write is the machine's only way to keep state
; outside its registers - and the program and its variable share the
; same 16 bytes.

        LDI 0
        STA i        ; i = 0
loop:   LDA i        ; A = i
        OUT
        ADD one      ; A = i + 1
        STA i        ; i = i + 1
        JMP loop
i:      .DB 0        ; the variable (entered into RAM with the program)
one:    .DB 1
