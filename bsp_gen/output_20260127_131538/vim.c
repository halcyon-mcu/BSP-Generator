/**
 * @file vim.c
 * @brief VIM driver implementation for TI RM46
 */

#include "vim.h"
#include <stdint.h>

/* ------------------------------------------------------------------------- */
/* Register access macro                                                     */
/* ------------------------------------------------------------------------- */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* ------------------------------------------------------------------------- */
/* VIM register addresses (from FACTS MIRROR)                                */
/* ------------------------------------------------------------------------- */
#define VIM_BASE                 (0xFFFFFE00u)
#define VIM_PARITY_BASE          (0xFFFFFD00u)

#define VIM_IRQINDEX_OFFSET      (0x0000u)
#define VIM_FIQINDEX_OFFSET      (0x0004u)
#define VIM_FIRQPR0_OFFSET       (0x0010u)
#define VIM_FIRQPR1_OFFSET       (0x0014u)
#define VIM_FIRQPR2_OFFSET       (0x0018u)
#define VIM_FIRQPR3_OFFSET       (0x001Cu)
#define VIM_INTREQ0_OFFSET       (0x0020u)
#define VIM_INTREQ1_OFFSET       (0x0024u)
#define VIM_INTREQ2_OFFSET       (0x0028u)
#define VIM_INTREQ3_OFFSET       (0x002Cu)
#define VIM_REQENASET0_OFFSET    (0x0030u)
#define VIM_REQENASET1_OFFSET    (0x0034u)
#define VIM_REQENASET2_OFFSET    (0x0038u)
#define VIM_REQENASET3_OFFSET    (0x003Cu)
#define VIM_REQENACLR0_OFFSET    (0x0040u)
#define VIM_REQENACLR1_OFFSET    (0x0044u)
#define VIM_REQENACLR2_OFFSET    (0x0048u)
#define VIM_REQENACLR3_OFFSET    (0x004Cu)

#define VIM_PARCTL_OFFSET        (0x00F0u)
#define VIM_PARFLG_OFFSET        (0x00ECu)
#define VIM_ADDERR_OFFSET        (0x00F4u)
#define VIM_FBPARERR_OFFSET      (0x00F8u)

/* VIM vector table (from FACTS MIRROR: soc.yaml VIM x-ext) */
#define VIM_VECTOR_TABLE_BASE    (0xFFF82000u)
#define VIM_VECTOR_TABLE_ENTRIES (128u)
#define VIM_VECTOR_TABLE_ENTRY_SIZE (4u)
#define VIM_PHANTOM_ENTRY        (0u)
#define VIM_RESERVED_CHANNEL     (127u)

#define VIM_PARITY_ENABLE_VALUE  (0x00000001u)

/* ------------------------------------------------------------------------- */
/* Default ISR (installed in all vector table entries at init)              */
/* ------------------------------------------------------------------------- */
static void vim_default_isr(void);

/* ------------------------------------------------------------------------- */
/* vim_init                                                                  */
/* ------------------------------------------------------------------------- */
void vim_init(void)
{
    uint32_t i;
    uint32_t vector_addr;

    /* Enable VIM RAM parity checking if supported */
    /* [prov] regs.yaml:VIM_PARITY.PARCTL */
    REG32(VIM_PARITY_BASE + VIM_PARCTL_OFFSET) = VIM_PARITY_ENABLE_VALUE;

    /* Initialize all vector table entries to default handler.
       Channel N uses entry (N + 1) due to phantom entry at index 0. */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    for (i = 0u; i < VIM_VECTOR_TABLE_ENTRIES; i++)
    {
        vector_addr = VIM_VECTOR_TABLE_BASE + (i * VIM_VECTOR_TABLE_ENTRY_SIZE);
        REG32(vector_addr) = (uint32_t)&vim_default_isr;
    }
}

/* ------------------------------------------------------------------------- */
/* vim_register_isr                                                          */
/* ------------------------------------------------------------------------- */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr)
{
    uint32_t vector_addr;

    /* Reject reserved channel or out-of-range */
    if (channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u) ||
        channel_id == VIM_RESERVED_CHANNEL)
    {
        return -1;
    }

    /* Channel N uses entry (N + 1) in the vector table */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    vector_addr = VIM_VECTOR_TABLE_BASE +
                  ((channel_id + 1u) * VIM_VECTOR_TABLE_ENTRY_SIZE);
    REG32(vector_addr) = (uint32_t)isr;

    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_enable_channel                                                        */
/* ------------------------------------------------------------------------- */
int vim_enable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    volatile uint32_t *reqenaset_reg;

    /* Reject reserved channel or out-of-range */
    if (channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u) ||
        channel_id == VIM_RESERVED_CHANNEL)
    {
        return -1;
    }

    /* Determine which REQENASET register (0..3) and bit position */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENASET0..3 */
    switch (reg_index)
    {
        case 0u:
            reqenaset_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENASET0_OFFSET);
            break;
        case 1u:
            reqenaset_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENASET1_OFFSET);
            break;
        case 2u:
            reqenaset_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENASET2_OFFSET);
            break;
        case 3u:
            reqenaset_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENASET3_OFFSET);
            break;
        default:
            return -1;
    }

    *reqenaset_reg = (1u << bit_pos);

    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_disable_channel                                                       */
/* ------------------------------------------------------------------------- */
int vim_disable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    volatile uint32_t *reqenaclr_reg;

    /* Reject reserved channel or out-of-range */
    if (channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u) ||
        channel_id == VIM_RESERVED_CHANNEL)
    {
        return -1;
    }

    /* Determine which REQENACLR register (0..3) and bit position */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENACLR0..3 */
    switch (reg_index)
    {
        case 0u:
            reqenaclr_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENACLR0_OFFSET);
            break;
        case 1u:
            reqenaclr_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENACLR1_OFFSET);
            break;
        case 2u:
            reqenaclr_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENACLR2_OFFSET);
            break;
        case 3u:
            reqenaclr_reg = (volatile uint32_t *)(VIM_BASE + VIM_REQENACLR3_OFFSET);
            break;
        default:
            return -1;
    }

    *reqenaclr_reg = (1u << bit_pos);

    return 0;
}

/* ------------------------------------------------------------------------- */
/* vim_set_fiq                                                               */
/* ------------------------------------------------------------------------- */
int vim_set_fiq(uint32_t channel_id, int enable_fiq)
{
    uint32_t reg_index;
    uint32_t bit_pos;
    volatile uint32_t *firqpr_reg;
    uint32_t val;

    /* Reject reserved channel or out-of-range */
    if (channel_id >= (VIM_VECTOR_TABLE_ENTRIES - 1u) ||
        channel_id == VIM_RESERVED_CHANNEL)
    {
        return -1;
    }

    /* Determine which FIRQPR register (0..3) and bit position */
    reg_index = channel_id / 32u;
    bit_pos = channel_id % 32u;

    /* [prov] regs.yaml:VIM.FIRQPR0..3 */
    switch (reg_index)
    {
        case 0u:
            firqpr_reg = (volatile uint32_t *)(VIM_BASE + VIM_FIRQPR0_OFFSET);
            break;
        case 1u:
            firqpr_reg = (volatile uint32_t *)(VIM_BASE + VIM_FIRQPR1_OFFSET);
            break;
        case 2u:
            firqpr_reg = (volatile uint32_t *)(VIM_BASE + VIM_FIRQPR2_OFFSET);
            break;
        case 3u:
            firqpr_reg = (volatile uint32_t *)(VIM_BASE + VIM_FIRQPR3_OFFSET);
            break;
        default:
            return -1;
    }

    val = *firqpr_reg;

    if (enable_fiq)
    {
        val |= (1u << bit_pos);
    }
    else
    {
        val &= ~(1u << bit_pos);
    }

    *firqpr_reg = val;

    return 0;
}

/* ------------------------------------------------------------------------- */
/* Default ISR (infinite loop trap)                                          */
/* ------------------------------------------------------------------------- */
static void vim_default_isr(void)
{
    while (1)
    {
        /* Trap unhandled interrupt */
    }
}