/**
 * @file vim.c
 * @brief VIM driver implementation for TI RM46
 */

#include "vim.h"

/* ------------------------------------------------------------------------- */
/* Register Access Macro */
/* ------------------------------------------------------------------------- */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* ------------------------------------------------------------------------- */
/* FACTS: VIM Base and Register Offsets */
/* ------------------------------------------------------------------------- */
/* [prov] regs.yaml:VIM.base_address */
#define VIM_BASE 0xFFFFFE00u

/* [prov] regs.yaml:VIM_PARITY.base_address */
#define VIM_PARITY_BASE 0xFFFFFD00u

/* [prov] regs.yaml:VIM.FIRQPR0..3 */
#define VIM_FIRQPR0_OFFSET 0x0010u
#define VIM_FIRQPR1_OFFSET 0x0014u
#define VIM_FIRQPR2_OFFSET 0x0018u
#define VIM_FIRQPR3_OFFSET 0x001Cu

/* [prov] regs.yaml:VIM.REQENASET0..3 */
#define VIM_REQENASET0_OFFSET 0x0030u
#define VIM_REQENASET1_OFFSET 0x0034u
#define VIM_REQENASET2_OFFSET 0x0038u
#define VIM_REQENASET3_OFFSET 0x003Cu

/* [prov] regs.yaml:VIM.REQENACLR0..3 */
#define VIM_REQENACLR0_OFFSET 0x0040u
#define VIM_REQENACLR1_OFFSET 0x0044u
#define VIM_REQENACLR2_OFFSET 0x0048u
#define VIM_REQENACLR3_OFFSET 0x004Cu

/* [prov] regs.yaml:VIM_PARITY.PARCTL */
#define VIM_PARITY_PARCTL_OFFSET 0x00F0u

/* [prov] soc.yaml:VIM.x-ext.parity.enable_value */
#define VIM_PARITY_ENABLE_VALUE 0x00000001u

/* ------------------------------------------------------------------------- */
/* FACTS: VIM Vector Table */
/* ------------------------------------------------------------------------- */
/* [prov] soc.yaml:VIM.x-ext.vector_table.base_address */
#define VIM_VECTOR_TABLE_BASE 0xFFF82000u

/* [prov] soc.yaml:VIM.x-ext.vector_table.entries */
#define VIM_VECTOR_TABLE_ENTRIES 128u

/* [prov] soc.yaml:VIM.x-ext.vector_table.entry_size_bytes */
#define VIM_VECTOR_TABLE_ENTRY_SIZE 4u

/* [prov] soc.yaml:VIM.x-ext.vector_table.phantom_entry */
#define VIM_PHANTOM_ENTRY 0u

/* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels[0] */
#define VIM_RESERVED_CHANNEL 127u

/* ------------------------------------------------------------------------- */
/* Default ISR */
/* ------------------------------------------------------------------------- */
/**
 * @brief Default interrupt handler for unregistered or unhandled interrupts.
 *
 * This handler is assigned to all vector table entries at initialization.
 * It enters an infinite loop to catch spurious or unhandled interrupts.
 * @ingroup BSP_VIM
 */
static void vim_default_isr(void)
{
    /* Infinite loop to catch unhandled interrupts */
    while (1)
    {
    }
}

/* ------------------------------------------------------------------------- */
/* vim_init */
/* ------------------------------------------------------------------------- */
void vim_init(void)
{
    uint32_t i;
    volatile uint32_t *vec_entry;

    /* Enable parity checking on VIM vector table RAM (if available) */
    /* [prov] regs.yaml:VIM_PARITY.PARCTL */
    REG32(VIM_PARITY_BASE + VIM_PARITY_PARCTL_OFFSET) = VIM_PARITY_ENABLE_VALUE;

    /* Initialize all vector table entries to default ISR */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    for (i = 0u; i < VIM_VECTOR_TABLE_ENTRIES; i++)
    {
        vec_entry = (volatile uint32_t *)(VIM_VECTOR_TABLE_BASE + (i * VIM_VECTOR_TABLE_ENTRY_SIZE));
        *vec_entry = (uint32_t)&vim_default_isr;
    }
}

/* ------------------------------------------------------------------------- */
/* vim_register_isr */
/* ------------------------------------------------------------------------- */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr)
{
    volatile uint32_t *vec_entry;
    uint32_t table_index;

    /* Validate channel ID: must be < 127 and not reserved */
    /* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels */
    if ((channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u)) || (channel_id == VIM_RESERVED_CHANNEL))
    {
        return -1;
    }

    /* VIM vector table entry for channel N is at index (N + 1) due to phantom entry */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    table_index = channel_id + 1u;
    vec_entry = (volatile uint32_t *)(VIM_VECTOR_TABLE_BASE + (table_index * VIM_VECTOR_TABLE_ENTRY_SIZE));
    *vec_entry = (uint32_t)isr;

    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_enable_channel */
/* ------------------------------------------------------------------------- */
int vim_enable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_offset;

    /* Validate channel ID: must be < 127 and not reserved */
    /* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels */
    if ((channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u)) || (channel_id == VIM_RESERVED_CHANNEL))
    {
        return -1;
    }

    /* Channels 0..31 => REQENASET0, 32..63 => REQENASET1, etc. */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENASET0..3 */
    switch (reg_index)
    {
    case 0u:
        reg_offset = VIM_REQENASET0_OFFSET;
        break;
    case 1u:
        reg_offset = VIM_REQENASET1_OFFSET;
        break;
    case 2u:
        reg_offset = VIM_REQENASET2_OFFSET;
        break;
    case 3u:
        reg_offset = VIM_REQENASET3_OFFSET;
        break;
    default:
        return -1;
    }

    REG32(VIM_BASE + reg_offset) = (1u << bit_pos);
    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_disable_channel */
/* ------------------------------------------------------------------------- */
int vim_disable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_offset;

    /* Validate channel ID: must be < 127 and not reserved */
    /* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels */
    if ((channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u)) || (channel_id == VIM_RESERVED_CHANNEL))
    {
        return -1;
    }

    /* Channels 0..31 => REQENACLR0, 32..63 => REQENACLR1, etc. */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENACLR0..3 */
    switch (reg_index)
    {
    case 0u:
        reg_offset = VIM_REQENACLR0_OFFSET;
        break;
    case 1u:
        reg_offset = VIM_REQENACLR1_OFFSET;
        break;
    case 2u:
        reg_offset = VIM_REQENACLR2_OFFSET;
        break;
    case 3u:
        reg_offset = VIM_REQENACLR3_OFFSET;
        break;
    default:
        return -1;
    }

    REG32(VIM_BASE + reg_offset) = (1u << bit_pos);
    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_set_fiq */
/* ------------------------------------------------------------------------- */
int vim_set_fiq(uint32_t channel_id, int enable_fiq)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    uint32_t reg_offset;
    uint32_t reg_val;

    /* Validate channel ID: must be < 127 and not reserved */
    /* [prov] soc.yaml:VIM.x-ext.vector_table.reserved_channels */
    if ((channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u)) || (channel_id == VIM_RESERVED_CHANNEL))
    {
        return -1;
    }

    /* Channels 0..31 => FIRQPR0, 32..63 => FIRQPR1, etc. */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.FIRQPR0..3 */
    switch (reg_index)
    {
    case 0u:
        reg_offset = VIM_FIRQPR0_OFFSET;
        break;
    case 1u:
        reg_offset = VIM_FIRQPR1_OFFSET;
        break;
    case 2u:
        reg_offset = VIM_FIRQPR2_OFFSET;
        break;
    case 3u:
        reg_offset = VIM_FIRQPR3_OFFSET;
        break;
    default:
        return -1;
    }

    reg_val = REG32(VIM_BASE + reg_offset);
    if (enable_fiq)
    {
        reg_val |= (1u << bit_pos);
    }
    else
    {
        reg_val &= ~(1u << bit_pos);
    }
    REG32(VIM_BASE + reg_offset) = reg_val;

    return 0;
}