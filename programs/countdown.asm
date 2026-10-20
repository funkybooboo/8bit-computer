; countdown.asm - count down from 255 to 0, then halt
;
; 0 - 1 underflows to 255 through the adder (SUB computes A + ~B + 1),
; so a register starting at 0 counts down from 255. SUB also sets the
; flags: ZF=1 when the count reaches 0, which ends the loop.

        LDI 0        ; A = 0
        SUB one      ; A = 0 - 1 = 255 (underflow, borrow)
loop:   OUT          ; display the count
        NOP          ; pacing: 6 idle microsteps slow the countdown
        SUB one      ; count down
        JZ  done     ; ZF=1 when A hit 0
        JMP loop
done:   OUT          ; display the final 0
        HLT
one:    .DB 1        ; the step down
