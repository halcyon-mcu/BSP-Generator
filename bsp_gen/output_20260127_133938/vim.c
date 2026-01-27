/**
 * @file vim.c
 * @brief VIM driver implementation for TI RM46
 */

#include "vim.h"
#include <stdint.h>

/* ========================================================================
 * VIM Register Access Macros
 * ======================================================================== */

/**
 * @brief 32-bit register access macro.
 */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* VIM base addresses */
/* [prov] regs.yaml:VIM.base_address */
#define VIM_BASE (0xFFFFFE00u)

/* [prov] regs.yaml:VIM_PARITY.base_address */
#define VIM_PARITY_BASE (0xFFFFFD00u)

/* VIM register offsets */
/* [prov] regs.yaml:VIM.FIRQPR0 */
#define VIM_FIRQPR0_OFFSET (0x0010u)
/* [prov] regs.yaml:VIM.FIRQPR1 */
#define VIM_FIRQPR1_OFFSET (0x0014u)
/* [prov] regs.yaml:VIM.FIRQPR2 */
#define VIM_FIRQPR2_OFFSET (0x0018u)
/* [prov] regs.yaml:VIM.FIRQPR3 */
#define VIM_FIRQPR3_OFFSET (0x001Cu)

/* [prov] regs.yaml:VIM.REQENASET0 */
#define VIM_REQENASET0_OFFSET (0x0030u)
/* [prov] regs.yaml:VIM.REQENASET1 */
#define VIM_REQENASET1_OFFSET (0x0034u)
/* [prov] regs.yaml:VIM.REQENASET2 */
#define VIM_REQENASET2_OFFSET (0x0038u)
/* [prov] regs.yaml:VIM.REQENASET3 */
#define VIM_REQENASET3_OFFSET (0x003Cu)

/* [prov] regs.yaml:VIM.REQENACLR0 */
#define VIM_REQENACLR0_OFFSET (0x0040u)
/* [prov] regs.yaml:VIM.REQENACLR1 */
#define VIM_REQENACLR1_OFFSET (0x0044u)
/* [prov] regs.yaml:VIM.REQENACLR2 */
#define VIM_REQENACLR2_OFFSET (0x0048u)
/* [prov] regs.yaml:VIM.REQENACLR3 */
#define VIM_REQENACLR3_OFFSET (0x004Cu)

/* VIM parity register offset */
/* [prov] regs.yaml:VIM_PARITY.PARCTL */
#define VIM_PARITY_PARCTL_OFFSET (0x00F0u)

/* VIM vector table constants */
/* [prov] soc.yaml:VIM.x-ext.vector_table.base_address */
#define VIM_VECTOR_TABLE_BASE (0xFFF82000u)
/* [prov] soc.yaml:VIM.x-ext.vector_table.entries */
#define VIM_VECTOR_TABLE_ENTRIES (128u)
/* [prov] soc.yaml:VIM.x-ext.vector_table.entry_size_bytes */
#define VIM_VECTOR_TABLE_ENTRY_SIZE (4u)
/* [prov] soc.yaml:VIM.x-ext.vector_table.phantom_entry */
#define VIM_VECTOR_TABLE_PHANTOM_ENTRY (0u)
/* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels */
#define VIM_RESERVED_CHANNEL_127 (127u)

/* [prov] soc.yaml:VIM.x-ext.parity.enable_value */
#define VIM_PARITY_ENABLE_VALUE (0x00000001u)

/* Maximum valid channel */
#define VIM_MAX_VALID_CHANNEL (126u)

/* ========================================================================
 * Static (private) functions
 * ======================================================================== */

/**
 * @brief Default ISR handler for uninitialized interrupt vectors.
 *
 * This handler is installed in all vector table entries during vim_init().
 * If an interrupt fires for a channel that has no user-registered ISR,
 * this handler will be invoked. It simply loops indefinitely.
 */
static void vim_default_isr(void)
{
    while (1)
    {
        /* Spin forever on unexpected interrupt */
    }
}

/**
 * @brief Check if a channel ID is valid.
 *
 * A valid channel is in the range [0..126] and is not reserved (127).
 *
 * @param[in] channel_id  Channel ID to validate
 * @return 1 if valid, 0 if invalid
 */
static int vim_is_channel_valid(uint32_t channel_id)
{
    if (channel_id > VIM_MAX_VALID_CHANNEL)
    {
        return 0;
    }
    if (channel_id == VIM_RESERVED_CHANNEL_127)
    {
        return 0;
    }
    return 1;
}

/* ========================================================================
 * Public API Implementation
 * ======================================================================== */

void vim_init(void)
{
    uint32_t i;
    volatile uint32_t *vector_table;

    /* Enable VIM parity checking */
    /* [prov] regs.yaml:VIM_PARITY.PARCTL */
    REG32(VIM_PARITY_BASE + VIM_PARITY_PARCTL_OFFSET) = VIM_PARITY_ENABLE_VALUE;

    /* Initialize all vector table entries to default handler */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    vector_table = (volatile uint32_t *)VIM_VECTOR_TABLE_BASE;

    for (i = 0u; i < VIM_VECTOR_TABLE_ENTRIES; i++)
    {
        vector_table[i] = (uint32_t)&vim_default_isr;
    }

    /* All channels remain disabled (REQENASET registers are zero at reset) */
}

int vim_register_isr(uint32_t channel_id, vim_isr_t isr)
{
    volatile uint32_t *vector_table;
    uint32_t vector_index;

    /* Validate inputs */
    if (!vim_is_channel_valid(channel_id))
    {
        return -1;
    }
    if (isr == (vim_isr_t)0)
    {
        return -1;
    }

    /* Channel N uses vector table entry (N + 1) because entry 0 is phantom */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    vector_table = (volatile uint32_t *)VIM_VECTOR_TABLE_BASE;
    vector_index = channel_id + 1u;

    vector_table[vector_index] = (uint32_t)isr;

    return 0;
}

int vim_enable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    volatile uint32_t *reqenaset_base;

    /* Validate channel */
    if (!vim_is_channel_valid(channel_id))
    {
        return -1;
    }

    /* Each REQENASET register covers 32 channels */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENASET0 */
    reqenaset_base = (volatile uint32_t *)(VIM_BASE + VIM_REQENASET0_OFFSET);
    reqenaset_base[reg_index] = (1u << bit_pos);

    return 0;
}

int vim_disable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    volatile uint32_t *reqenaclr_base;

    /* Validate channel */
    if (!vim_is_channel_valid(channel_id))
    {
        return -1;
    }

    /* Each REQENACLR register covers 32 channels */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENACLR0 */
    reqenaclr_base = (volatile uint32_t *)(VIM_BASE + VIM_REQENACLR0_OFFSET);
    reqenaclr_base[reg_index] = (1u << bit_pos);

    return 0;
}

int vim_set_fiq(uint32_t channel_id, int enable_fiq)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t bit_mask;
    volatile uint32_t *firqpr_base;
    uint32_t reg_val;

    /* Validate channel */
    if (!vim_is_channel_valid(channel_id))
    {
        return -1;
    }

    /* Each FIRQPR register covers 32 channels */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;
    bit_mask = (1u << bit_pos);

    /* [prov] regs.yaml:VIM.FIRQPR0 */
    firqpr_base = (volatile uint32_t *)(VIM_BASE + VIM_FIRQPR0_OFFSET);

    /* Read-modify-write: set or clear the FIQ bit */
    reg_val = firqpr_base[reg_index];
    if (enable_fiq)
    {
        reg_val |= bit_mask;
    }
    else
    {
        reg_val &= ~bit_mask;
    }
    firqpr_base[reg_index] = reg_val;

    return 0;
}