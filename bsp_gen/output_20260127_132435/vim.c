/**
 * @file vim.c
 * @brief TI RM46 Vectored Interrupt Manager (VIM) driver implementation
 */

#include "vim.h"
#include <stdint.h>

/* ========================================================================== */
/*                             Macro definitions                              */
/* ========================================================================== */

/**
 * @brief Register access macro for 32-bit peripherals.
 */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* VIM base addresses from FACTS MIRROR */
#define VIM_BASE                        (0xFFFFFE00u)
#define VIM_PARITY_BASE                 (0xFFFFFD00u)

/* VIM register offsets from FACTS MIRROR */
#define VIM_IRQINDEX_OFFSET             (0x0000u)
#define VIM_FIQINDEX_OFFSET             (0x0004u)
#define VIM_FIRQPR0_OFFSET              (0x0010u)
#define VIM_FIRQPR1_OFFSET              (0x0014u)
#define VIM_FIRQPR2_OFFSET              (0x0018u)
#define VIM_FIRQPR3_OFFSET              (0x001Cu)
#define VIM_INTREQ0_OFFSET              (0x0020u)
#define VIM_INTREQ1_OFFSET              (0x0024u)
#define VIM_INTREQ2_OFFSET              (0x0028u)
#define VIM_INTREQ3_OFFSET              (0x002Cu)
#define VIM_REQENASET0_OFFSET           (0x0030u)
#define VIM_REQENASET1_OFFSET           (0x0034u)
#define VIM_REQENASET2_OFFSET           (0x0038u)
#define VIM_REQENASET3_OFFSET           (0x003Cu)
#define VIM_REQENACLR0_OFFSET           (0x0040u)
#define VIM_REQENACLR1_OFFSET           (0x0044u)
#define VIM_REQENACLR2_OFFSET           (0x0048u)
#define VIM_REQENACLR3_OFFSET           (0x004Cu)
#define VIM_WAKENASET0_OFFSET           (0x0050u)
#define VIM_WAKENASET1_OFFSET           (0x0054u)
#define VIM_WAKENASET2_OFFSET           (0x0058u)
#define VIM_WAKENASET3_OFFSET           (0x005Cu)
#define VIM_WAKENACLR0_OFFSET           (0x0060u)
#define VIM_WAKENACLR1_OFFSET           (0x0064u)
#define VIM_WAKENACLR2_OFFSET           (0x0068u)
#define VIM_WAKENACLR3_OFFSET           (0x006Cu)
#define VIM_IRQVECREG_OFFSET            (0x0070u)
#define VIM_FIQVECREG_OFFSET            (0x0074u)
#define VIM_CAPEVT_OFFSET               (0x0078u)
#define VIM_CHANCTRL0_OFFSET            (0x0080u)

/* VIM_PARITY register offsets from FACTS MIRROR */
#define VIM_PARITY_PARFLG_OFFSET        (0x00ECu)
#define VIM_PARITY_PARCTL_OFFSET        (0x00F0u)
#define VIM_PARITY_ADDERR_OFFSET        (0x00F4u)
#define VIM_PARITY_FBPARERR_OFFSET      (0x00F8u)

/* VIM vector table configuration from FACTS MIRROR */
#define VIM_VECTOR_TABLE_BASE           (0xFFF82000u)
#define VIM_VECTOR_TABLE_ENTRIES        (128u)
#define VIM_VECTOR_TABLE_ENTRY_SIZE     (4u)
#define VIM_VECTOR_TABLE_PHANTOM_ENTRY  (0u)
#define VIM_VECTOR_TABLE_RESERVED_CH    (127u)

/* VIM parity enable value from FACTS MIRROR */
#define VIM_PARITY_ENABLE_VALUE         (0x00000001u)

/* Maximum valid channel ID (126, since 127 is reserved) */
#define VIM_MAX_CHANNEL_ID              (126u)

/* ========================================================================== */
/*                           Function declarations                            */
/* ========================================================================== */

static void vim_default_isr(void);
static int vim_is_valid_channel(uint32_t channel_id);

/* ========================================================================== */
/*                            Function definitions                            */
/* ========================================================================== */

/**
 * @brief Default ISR for unhandled interrupts.
 * @ingroup BSP_VIM
 *
 * This function is called when an interrupt occurs for a channel that has not
 * been assigned a user ISR. The default behavior is an infinite loop.
 *
 * @note User may override this weak symbol to handle unexpected interrupts.
 */
static void vim_default_isr(void)
{
    /* Infinite loop for unhandled interrupts */
    while (1)
    {
        /* Wait indefinitely */
    }
}

/**
 * @brief Validate a VIM channel ID.
 *
 * @param[in] channel_id VIM channel number
 * @return 1 if valid, 0 if invalid or reserved
 */
static int vim_is_valid_channel(uint32_t channel_id)
{
    if (channel_id > VIM_MAX_CHANNEL_ID)
    {
        return 0;
    }
    if (channel_id == VIM_VECTOR_TABLE_RESERVED_CH)
    {
        return 0;
    }
    return 1;
}

void vim_init(void)
{
    uint32_t i;
    volatile uint32_t *vec_entry;

    /* Step 1: Enable parity protection if supported */
    /* [prov] regs.yaml:VIM_PARITY.PARCTL */
    REG32(VIM_PARITY_BASE + VIM_PARITY_PARCTL_OFFSET) = VIM_PARITY_ENABLE_VALUE;

    /* Step 2: Initialize all vector table entries to default handler */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    for (i = 0; i < VIM_VECTOR_TABLE_ENTRIES; i++)
    {
        vec_entry = (volatile uint32_t *)(VIM_VECTOR_TABLE_BASE + (i * VIM_VECTOR_TABLE_ENTRY_SIZE));
        *vec_entry = (uint32_t)vim_default_isr;
    }

    /* Step 3: Do NOT enable any channels by default; user must enable explicitly */
}

int vim_register_isr(uint32_t channel_id, vim_isr_t isr)
{
    volatile uint32_t *vec_entry;
    uint32_t entry_index;

    /* Validate channel_id */
    if (!vim_is_valid_channel(channel_id))
    {
        return -1;
    }

    /* Validate ISR pointer */
    if (isr == (vim_isr_t)0)
    {
        return -1;
    }

    /* Compute vector table entry index: channel N uses entry (N + 1) */
    /* [prov] soc.yaml:VIM.x-ext.vector_table (base/entries) */
    entry_index = channel_id + 1u;

    vec_entry = (volatile uint32_t *)(VIM_VECTOR_TABLE_BASE + (entry_index * VIM_VECTOR_TABLE_ENTRY_SIZE));
    *vec_entry = (uint32_t)isr;

    return 0;
}

int vim_enable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_index;
    uint32_t reg_offset;

    /* Validate channel_id */
    if (!vim_is_valid_channel(channel_id))
    {
        return -1;
    }

    /* Determine which REQENASET register and bit position */
    reg_index = channel_id / 32u;
    bit_index = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENASET0..3 */
    switch (reg_index)
    {
        case 0:
            reg_offset = VIM_REQENASET0_OFFSET;
            break;
        case 1:
            reg_offset = VIM_REQENASET1_OFFSET;
            break;
        case 2:
            reg_offset = VIM_REQENASET2_OFFSET;
            break;
        case 3:
            reg_offset = VIM_REQENASET3_OFFSET;
            break;
        default:
            return -1;
    }

    REG32(VIM_BASE + reg_offset) = (1u << bit_index);

    return 0;
}

int vim_disable_channel(uint32_t channel_id)
{
    uint32_t reg_index;
    uint32_t bit_index;
    uint32_t reg_offset;

    /* Validate channel_id */
    if (!vim_is_valid_channel(channel_id))
    {
        return -1;
    }

    /* Determine which REQENACLR register and bit position */
    reg_index = channel_id / 32u;
    bit_index = channel_id % 32u;

    /* [prov] regs.yaml:VIM.REQENACLR0..3 */
    switch (reg_index)
    {
        case 0:
            reg_offset = VIM_REQENACLR0_OFFSET;
            break;
        case 1:
            reg_offset = VIM_REQENACLR1_OFFSET;
            break;
        case 2:
            reg_offset = VIM_REQENACLR2_OFFSET;
            break;
        case 3:
            reg_offset = VIM_REQENACLR3_OFFSET;
            break;
        default:
            return -1;
    }

    REG32(VIM_BASE + reg_offset) = (1u << bit_index);

    return 0;
}

int vim_set_fiq(uint32_t channel_id, int enable_fiq)
{
    uint32_t reg_index;
    uint32_t bit_index;
    uint32_t reg_offset;
    uint32_t reg_val;

    /* Validate channel_id */
    if (!vim_is_valid_channel(channel_id))
    {
        return -1;
    }

    /* Determine which FIRQPR register and bit position */
    reg_index = channel_id / 32u;
    bit_index = channel_id % 32u;

    /* [prov] regs.yaml:VIM.FIRQPR0..3 */
    switch (reg_index)
    {
        case 0:
            reg_offset = VIM_FIRQPR0_OFFSET;
            break;
        case 1:
            reg_offset = VIM_FIRQPR1_OFFSET;
            break;
        case 2:
            reg_offset = VIM_FIRQPR2_OFFSET;
            break;
        case 3:
            reg_offset = VIM_FIRQPR3_OFFSET;
            break;
        default:
            return -1;
    }

    /* Read-modify-write to set or clear the FIQ bit */
    reg_val = REG32(VIM_BASE + reg_offset);
    if (enable_fiq)
    {
        reg_val |= (1u << bit_index);
    }
    else
    {
        reg_val &= ~(1u << bit_index);
    }
    REG32(VIM_BASE + reg_offset) = reg_val;

    return 0;
}