;******************************************************************************
; start.s
;
; Minimal interrupt vector table and reset handler for TI RM46 (Cortex-R4)
; using TI ARM CGT assembler syntax.
;
; The vector table (.intvecs) contains the initial stack pointer and exception
; vectors. Reset_Handler initializes SP and branches to the C entry point.
;******************************************************************************

;------------------------------------------------------------------------------
; Interrupt Vector Table
;------------------------------------------------------------------------------
    .sect   ".intvecs"
    .align  4

    .long   end_of_stack        ; 0x00: Initial stack pointer
    .long   Reset_Handler       ; 0x04: Reset vector
    .long   Reset_Handler       ; 0x08: Undefined instruction
    .long   Reset_Handler       ; 0x0C: Supervisor call (SVC)
    .long   Reset_Handler       ; 0x10: Prefetch abort
    .long   Reset_Handler       ; 0x14: Data abort
    .long   0                   ; 0x18: Reserved
    .long   Reset_Handler       ; 0x1C: IRQ
    .long   Reset_Handler       ; 0x20: FIQ

;------------------------------------------------------------------------------
; Reset Handler
;------------------------------------------------------------------------------
    .sect   ".text"
    .align  4

    .global Reset_Handler
    .ref    Reset_Handler_C
    .ref    end_of_stack

Reset_Handler:
    ; Load stack pointer with end_of_stack address from linker script
    LDR     SP, stack_addr

    ; Branch to C entry point
    BL      Reset_Handler_C

    ; If Reset_Handler_C returns, loop forever
Reset_Loop:
    B       Reset_Loop

stack_addr:
    .long   end_of_stack

;------------------------------------------------------------------------------
; End of start.s
;------------------------------------------------------------------------------