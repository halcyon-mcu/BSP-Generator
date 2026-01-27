/**
 * @file vim.c
 * @brief VIM driver implementation for TI RM46.
 */

#include "vim.h"
#include <stdint.h>

/* -----------------------------------------------------------------------------
 * FACTS: Register addresses and offsets from regs.yaml and soc.yaml
 * ---------------------------------------------------------------------------*/

#define VIM_BASE                (0xFFFFFE00u)
#define VIM_PARITY_BASE         (0xFFFFFD00u)

#define VIM_FIRQPR0_OFFSET      (0x0010u)
#define VIM_FIRQPR1_OFFSET      (0x0014u)
#define VIM_FIRQPR2_OFFSET      (0x0018u)
#define VIM_FIRQPR3_OFFSET      (0x001Cu)

#define VIM_REQENASET0_OFFSET   (0x0030u)
#define VIM_REQENASET1_OFFSET   (0x0034u)
#define VIM_REQENASET2_OFFSET   (0x0038u)
#define VIM_REQENASET3_OFFSET   (0x003Cu)

#define VIM_REQENACLR0_OFFSET   (0x0040u)
#define VIM_REQENACLR1_OFFSET   (0x0044u)
#define VIM_REQENACLR2_OFFSET   (0x0048u)
#define VIM_REQENACLR3_OFFSET   (0x004Cu)

#define VIM_PARITY_PARCTL_OFFSET (0x00F0u)

#define VIM_VECTOR_TABLE_BASE   (0xFFF82000u)
#define VIM_VECTOR_TABLE_ENTRIES (128u)
#define VIM_RESERVED_CHANNEL     (127u)
#define VIM_PARITY_ENABLE_VALUE (0x00000001u)

/* Helper macro for 32-bit register access */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* -----------------------------------------------------------------------------
 * Internal declarations
 * ---------------------------------------------------------------------------*/

static void vim_default_isr(void);

/* -----------------------------------------------------------------------------
 * Public API implementation
 * ---------------------------------------------------------------------------*/

void vim_init(void)
{
    uint32_t i;
    uint32_t table_addr;

    /* [prov] soc.yaml:VIM.x-ext.parity.enable_reg + enable_value
     * Enable VIM parity checking before initializing vector table.
     */
    REG32(VIM_PARITY_BASE + VIM_PARITY_PARCTL_OFFSET) = VIM_PARITY_ENABLE_VALUE;

    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries)
     * Initialize all vector table entries to the default handler.
     * Entry 0 is phantom (not used). Channels 0..126 map to entries 1..127.
     * Channel 127 is reserved and should not be used, but we initialize entry 128 anyway.
     */
    table_addr = VIM_VECTOR_TABLE_BASE;
    for (i = 0u; i < VIM_VECTOR_TABLE_ENTRIES; i++) {
        REG32(table_addr + (i * 4u)) = (uint32_t)vim_default_isr;
    }
}

int vim_register_isr(uint32_t channel_id, vim_isr_t isr)
{
    uint32_t table_addr;
    uint32_t entry_index;

    /* Validate channel_id: must be <= 126 (channel 127 is reserved) */
    if (channel_id >= VIM_RESERVED_CHANNEL) {
        return -1;
    }

    /* Validate ISR pointer */
    if (isr == (vim_isr_t)0) {
        return -1;
    }

    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries)
     * Channel N maps to vector table entry (N + 1) because entry 0 is phantom.
     */
    entry_index = channel_id + 1u;
    table_addr = VIM_VECTOR_TABLE_BASE + (entry_index * 4u);

    REG32(table_addr) = (uint32_t)isr;

    return 0;
}

int vim_enable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_addr;

    /* Validate channel_id */
    if (channel_id >= VIM_RESERVED_CHANNEL) {
        return -1;
    }

    /* Determine which REQENASET register (0..3) and bit position (0..31) */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENASET0..3 */
    switch (reg_index) {
        case 0u:
            reg_addr = VIM_BASE + VIM_REQENASET0_OFFSET;
            break;
        case 1u:
            reg_addr = VIM_BASE + VIM_REQENASET1_OFFSET;
            break;
        case 2u:
            reg_addr = VIM_BASE + VIM_REQENASET2_OFFSET;
            break;
        case 3u:
            reg_addr = VIM_BASE + VIM_REQENASET3_OFFSET;
            break;
        default:
            return -1;
    }

    REG32(reg_addr) = (1u << bit_pos);

    return 0;
}

int vim_disable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_addr;

    /* Validate channel_id */
    if (channel_id >= VIM_RESERVED_CHANNEL) {
        return -1;
    }

    /* Determine which REQENACLR register (0..3) and bit position (0..31) */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENACLR0..3 */
    switch (reg_index) {
        case 0u:
            reg_addr = VIM_BASE + VIM_REQENACLR0_OFFSET;
            break;
        case 1u:
            reg_addr = VIM_BASE + VIM_REQENACLR1_OFFSET;
            break;
        case 2u:
            reg_addr = VIM_BASE + VIM_REQENACLR2_OFFSET;
            break;
        case 3u:
            reg_addr = VIM_BASE + VIM_REQENACLR3_OFFSET;
            break;
        default:
            return -1;
    }

    REG32(reg_addr) = (1u << bit_pos);

    return 0;
}

int vim_set_fiq(uint32_t channel_id, int enable_fiq)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_addr;
    uint32_t reg_val;

    /* Validate channel_id */
    if (channel_id >= VIM_RESERVED_CHANNEL) {
        return -1;
    }

    /* Determine which FIRQPR register (0..3) and bit position (0..31) */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.FIRQPR0..3 */
    switch (reg_index) {
        case 0u:
            reg_addr = VIM_BASE + VIM_FIRQPR0_OFFSET;
            break;
        case 1u:
            reg_addr = VIM_BASE + VIM_FIRQPR1_OFFSET;
            break;
        case 2u:
            reg_addr = VIM_BASE + VIM_FIRQPR2_OFFSET;
            break;
        case 3u:
            reg_addr = VIM_BASE + VIM_FIRQPR3_OFFSET;
            break;
        default:
            return -1;
    }

    /* Read-modify-write to set or clear the FIQ bit */
    reg_val = REG32(reg_addr);
    if (enable_fiq != 0) {
        reg_val |= (1u << bit_pos);
    } else {
        reg_val &= ~(1u << bit_pos);
    }
    REG32(reg_addr) = reg_val;

    return 0;
}

/* -----------------------------------------------------------------------------
 * Default ISR handler
 * ---------------------------------------------------------------------------*/

/**
 * @brief Default VIM interrupt handler.
 *
 * This weak handler is installed into all vector table entries during vim_init().
 * User code may override this symbol to provide a catch-all for unhandled interrupts,
 * or register individual channel handlers using vim_register_isr().
 *
 * By default, it enters an infinite loop to aid debugging.
 *
 * @note This function is called from interrupt context.
 */
static void vim_default_isr(void)
{
    /* Infinite loop to trap unhandled interrupts */
    while (1) {
        /* User may set breakpoint here to debug unexpected interrupts */
    }
}