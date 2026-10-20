; bits.asm - a byte on the display, one bit at a time
;
; The display shows bytes; this program shows the byte's *binary
; representation* - one bit per OUT, most significant first - the way
; a serial link sends it. Each lap rotates the byte left through carry
; (the rol.asm trick), remembers the bit that came off the top, and
; displays it as 0 or 1; after 8 laps the byte is back where it started
; and the pattern repeats. The shift register survives in RAM because
; LDI 0 / LDI 1 would overwrite A to display the bit. With x = 10110101
; the display reads 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, ... - the byte, as
; digits.

        LDA x
loop:   DBL             ; A = 2*A, CF = the top bit
        JNC zero        ; the bit was 0
        ADDI 1          ; rotate: wrap the carried bit into bit 0
        STA s
        LDI 1
        OUT             ; display the bit: 1
        JMP next
zero:   STA s
        LDI 0
        OUT             ; display the bit: 0
next:   LDA s           ; bring the rotating byte back
        JMP loop

x:      .DB 0b10110101  ; the byte to display, bit by bit
s:      .DB 0           ; the rotating copy of x
