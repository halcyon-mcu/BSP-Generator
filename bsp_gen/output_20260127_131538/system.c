/**
 * @file system.c
 * @brief System initialization implementation for TI Hercules RM46
 */

#include <stdint.h>
#include "system.h"
#include "clock.h"

/* Base addresses */
#define SYSTEM_BASE 0xFFFFFF00u
#define PCR_BASE    0xFFFFE000u

/* PCR register offsets */
#define PCR_PSPWRDWNCLR0_OFFSET 0x000000A0u
#define PCR_PSPWRDWNCLR1_OFFSET 0x000000A4u
#define PCR_PSPWRDWNCLR2_OFFSET 0x000000A8u
#define PCR_PSPWRDWNCLR3_OFFSET 0x000000ACu

/* SYSTEM register offsets */
#define SYSTEM_CLKCNTL_OFFSET   0x000000D0u

/* Operation codes */
#define OP_SET_BITS   1
#define OP_CLEAR_BITS 2
#define OP_WRITE      3

/**
 * @brief Perform a register operation (set/clear/write).
 * @ingroup BSP_SYSTEM
 *
 * @param base Base address of the peripheral.
 * @param offset Register offset from base.
 * @param value Value or mask to apply.
 * @param op Operation type (OP_SET_BITS, OP_CLEAR_BITS, OP_WRITE).
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

    /* [prov] soc.yaml:SYSTEM.init[0] -> PCR.PSPWRDWNCLR0 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR0_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] soc.yaml:SYSTEM.init[1] -> PCR.PSPWRDWNCLR1 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR1_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] soc.yaml:SYSTEM.init[2] -> PCR.PSPWRDWNCLR2 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR2_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] soc.yaml:SYSTEM.init[3] -> PCR.PSPWRDWNCLR3 */
    reg_write_op(PCR_BASE, PCR_PSPWRDWNCLR3_OFFSET, 0xFFFFFFFFu, OP_SET_BITS);

    /* [prov] soc.yaml:SYSTEM.init[4] -> SYSTEM.CLKCNTL */
    reg_write_op(SYSTEM_BASE, SYSTEM_CLKCNTL_OFFSET, 0x00000100u, OP_SET_BITS);

    /* Enable base clocks from SYSTEM.x-ext.base_clock_refs */
    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[0] -> OSCIN */
    clock_enable(CLOCKREF_OSCIN);

    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[1] -> HF_LPO */
    clock_enable(CLOCKREF_HF_LPO);

    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[2] -> LF_LPO */
    clock_enable(CLOCKREF_LF_LPO);

    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[3] -> GCLK */
    clock_enable(CLOCKREF_GCLK);

    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[4] -> HCLK */
    clock_enable(CLOCKREF_HCLK);

    /* [prov] soc.yaml:SYSTEM.x-ext.base_clock_refs[5] -> VCLK */
    clock_enable(CLOCKREF_VCLK);

    /* Clock configuration (PLL/dividers/mux) is application-owned; see clock_configure* APIs in clock.h (do not call here). */
}