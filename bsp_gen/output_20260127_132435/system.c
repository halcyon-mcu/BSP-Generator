/**
 * @file system.c
 * @brief System initialization implementation for TI RM46 Hercules MCU
 */

#include <stdint.h>
#include "system.h"
#include "clock.h"

/* SYSTEM peripheral base address */
#define SYSTEM_BASE 0xFFFFFF00u

/* PCR peripheral base address */
#define PCR_BASE 0xFFFFE000u

/* SYSTEM register offsets */
#define SYSTEM_CLKCNTL_OFFSET 0xD0u

/* PCR register offsets */
#define PCR_PSPWRDWNCLR0_OFFSET 0xA0u
#define PCR_PSPWRDWNCLR1_OFFSET 0xA4u
#define PCR_PSPWRDWNCLR2_OFFSET 0xA8u
#define PCR_PSPWRDWNCLR3_OFFSET 0xACu

/* Register operation types */
#define OP_SET_BITS   1
#define OP_CLEAR_BITS 2
#define OP_WRITE      3

/**
 * @brief Perform a register write operation
 *
 * @param base Base address of peripheral
 * @param offset Register offset from base
 * @param value Value to write or mask to apply
 * @param op Operation type (OP_SET_BITS, OP_CLEAR_BITS, or OP_WRITE)
 */
static void reg_write_op(uint32_t base, uint32_t offset, uint32_t value, int op)
{
    volatile uint32_t *reg;

    reg = (volatile uint32_t *)(base + offset);

    if (op == OP_SET_BITS) {
        *reg |= value;
    } else if (op == OP_CLEAR_BITS) {
        *reg &= ~value;
    } else if (op == OP_WRITE) {
        *reg = value;
    }
}

void system_init(void)
{
    /* Apply SYSTEM.x-ext.init register operations in order */

    /* [prov] regs.yaml:PCR.PSPWRDWNCLR0 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR0_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] regs.yaml:PCR.PSPWRDWNCLR1 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR1_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] regs.yaml:PCR.PSPWRDWNCLR2 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR2_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] regs.yaml:PCR.PSPWRDWNCLR3 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR3_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    reg_write_op(SYSTEM_BASE, SYSTEM_CLKCNTL_OFFSET, 0x00000100u, OP_SET_BITS);

    /* Enable base clocks listed in SYSTEM.x-ext.base_clock_refs */
    clock_enable(CLOCKREF_OSCIN);
    clock_enable(CLOCKREF_HF_LPO);
    clock_enable(CLOCKREF_LF_LPO);
    clock_enable(CLOCKREF_GCLK);
    clock_enable(CLOCKREF_HCLK);
    clock_enable(CLOCKREF_VCLK);

    /* Clock configuration (PLL/dividers/mux) is application-owned; see clock_configure* APIs in clock.h (do not call here). */
}