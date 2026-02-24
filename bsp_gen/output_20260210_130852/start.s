;******************************************************************************
; start.s
;
; Minimal ARM Cortex-R4 startup code for TI RM46 (Hercules) using TI ARM CGT.
;
; Provides:
;   - Interrupt vector table (.intvecs section)
;   - Reset_Handler that initializes SP and branches to C entry point
;******************************************************************************

;------------------------------------------------------------------------------
; Interrupt Vector Table
;------------------------------------------------------------------------------
    .sect   ".intvecs"
    .align  4

    .long   end_of_stack          ; 0x00: Initial stack pointer
    .long   Reset_Handler         ; 0x04: Reset vector
    .long   Reset_Handler         ; 0x08: Undefined instruction
    .long   Reset_Handler         ; 0x0C: Supervisor call (SVC)
    .long   Reset_Handler         ; 0x10: Prefetch abort
    .long   Reset_Handler         ; 0x14: Data abort
    .long   0                     ; 0x18: Reserved
    .long   Reset_Handler         ; 0x1C: IRQ
    .long   Reset_Handler         ; 0x20: FIQ

;------------------------------------------------------------------------------
; Reset Handler Code Section
;------------------------------------------------------------------------------
    .sect   ".text"
    .align  4

    .global Reset_Handler
    .ref    Reset_Handler_C
    .ref    end_of_stack

;------------------------------------------------------------------------------
; Reset_Handler
;
; Entry point on reset. Initializes the stack pointer and branches to the
; C runtime initialization function Reset_Handler_C.
;
; If Reset_Handler_C returns, execution enters an infinite loop.
;------------------------------------------------------------------------------
Reset_Handler:
    LDR   SP, stack_addr          ; Load stack pointer from end_of_stack
    BL    Reset_Handler_C         ; Branch with link to C entry point

Reset_Loop:
    B     Reset_Loop              ; Infinite loop if C code returns

;------------------------------------------------------------------------------
; Literal pool for stack address
;------------------------------------------------------------------------------
    .align  4
stack_addr:
    .long   end_of_stack

;------------------------------------------------------------------------------
; End of start.s
;------------------------------------------------------------------------------