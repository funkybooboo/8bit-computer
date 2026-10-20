; overflow.asm - count by 60 until the adder carries, then halt
;
; ADD wraps mod 256 and sets CF=1 when the sum overflows the byte, so
; JC doubles as an overflow detector: 0, 60, 120, 180, 240, then the
; fifth add carries (240 + 60 = 44) and the program halts.

        LDI 0
loop:   OUT          ; display the running sum
        ADD sixty    ; wraps at 240 + 60 = 44, CF=1
        JC  done     ; carry = the byte overflowed
        JMP loop
done:   HLT
sixty:  .DB 60
