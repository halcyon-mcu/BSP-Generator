/**
 * @file sci.c
 * @brief SCI/LIN driver implementation for TI RM46.
 */

#include <stdint.h>
#include "sci.h"
#include "clock.h"

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* SCI base address */
#define SCI_BASE (0xFFF7E400u)

/* SCI register offsets */
#define SCIGCR0_OFFSET   (0x00u)
#define SCIGCR1_OFFSET   (0x04u)
#define SCIGCR2_OFFSET   (0x08u)
#define SCISETINT_OFFSET (0x0Cu)
#define SCICLEARINT_OFFSET (0x10u)
#define SCISETINTLVL_OFFSET (0x14u)
#define SCICLEARINTLVL_OFFSET (0x18u)
#define SCIFLR_OFFSET    (0x1Cu)
#define SCIINTVECT0_OFFSET (0x20u)
#define SCIINTVECT1_OFFSET (0x24u)
#define SCIFORMAT_OFFSET (0x28u)
#define BRS_OFFSET       (0x2Cu)
#define SCIED_OFFSET     (0x30u)
#define SCIRD_OFFSET     (0x34u)
#define SCITD_OFFSET     (0x38u)
#define SCIPIO0_OFFSET   (0x3Cu)
#define SCIPIO1_OFFSET   (0x40u)
#define SCIPIO2_OFFSET   (0x44u)
#define SCIPIO3_OFFSET   (0x48u)
#define SCIPIO4_OFFSET   (0x4Cu)
#define SCIPIO5_OFFSET   (0x50u)
#define SCIPIO6_OFFSET   (0x54u)
#define SCIPIO7_OFFSET   (0x58u)
#define SCIPIO8_OFFSET   (0x5Cu)
#define LINCOMPARE_OFFSET (0x60u)
#define LINRD0_OFFSET    (0x64u)
#define LINRD1_OFFSET    (0x68u)
#define LINMASK_OFFSET   (0x6Cu)
#define LINID_OFFSET     (0x70u)
#define LINTD0_OFFSET    (0x74u)
#define LINTD1_OFFSET    (0x78u)
#define MBRS_OFFSET      (0x7Cu)
#define IODFTCTRL_OFFSET (0x90u)

/* SCI register addresses */
#define SCIGCR0   REG32(SCI_BASE + SCIGCR0_OFFSET)
#define SCIGCR1   REG32(SCI_BASE + SCIGCR1_OFFSET)
#define SCIGCR2   REG32(SCI_BASE + SCIGCR2_OFFSET)
#define SCISETINT REG32(SCI_BASE + SCISETINT_OFFSET)
#define SCICLEARINT REG32(SCI_BASE + SCICLEARINT_OFFSET)
#define SCISETINTLVL REG32(SCI_BASE + SCISETINTLVL_OFFSET)
#define SCICLEARINTLVL REG32(SCI_BASE + SCICLEARINTLVL_OFFSET)
#define SCIFLR    REG32(SCI_BASE + SCIFLR_OFFSET)
#define SCIINTVECT0 REG32(SCI_BASE + SCIINTVECT0_OFFSET)
#define SCIINTVECT1 REG32(SCI_BASE + SCIINTVECT1_OFFSET)
#define SCIFORMAT REG32(SCI_BASE + SCIFORMAT_OFFSET)
#define BRS       REG32(SCI_BASE + BRS_OFFSET)
#define SCIED     REG32(SCI_BASE + SCIED_OFFSET)
#define SCIRD     REG32(SCI_BASE + SCIRD_OFFSET)
#define SCITD     REG32(SCI_BASE + SCITD_OFFSET)
#define SCIPIO0   REG32(SCI_BASE + SCIPIO0_OFFSET)
#define SCIPIO1   REG32(SCI_BASE + SCIPIO1_OFFSET)
#define SCIPIO2   REG32(SCI_BASE + SCIPIO2_OFFSET)
#define SCIPIO3   REG32(SCI_BASE + SCIPIO3_OFFSET)
#define SCIPIO4   REG32(SCI_BASE + SCIPIO4_OFFSET)
#define SCIPIO5   REG32(SCI_BASE + SCIPIO5_OFFSET)
#define SCIPIO6   REG32(SCI_BASE + SCIPIO6_OFFSET)
#define SCIPIO7   REG32(SCI_BASE + SCIPIO7_OFFSET)
#define SCIPIO8   REG32(SCI_BASE + SCIPIO8_OFFSET)
#define LINCOMPARE REG32(SCI_BASE + LINCOMPARE_OFFSET)
#define LINRD0    REG32(SCI_BASE + LINRD0_OFFSET)
#define LINRD1    REG32(SCI_BASE + LINRD1_OFFSET)
#define LINMASK   REG32(SCI_BASE + LINMASK_OFFSET)
#define LINID     REG32(SCI_BASE + LINID_OFFSET)
#define LINTD0    REG32(SCI_BASE + LINTD0_OFFSET)
#define LINTD1    REG32(SCI_BASE + LINTD1_OFFSET)
#define MBRS      REG32(SCI_BASE + MBRS_OFFSET)
#define IODFTCTRL REG32(SCI_BASE + IODFTCTRL_OFFSET)

/* External VIM API declarations */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Static helper: wait for a status bit with timeout */
static int sci_wait_for_flag(uint32_t flag_mask, uint32_t timeout_cycles)
{
    uint32_t count;
    count = 0u;
    while ((SCIFLR & flag_mask) == 0u) {
        if (timeout_cycles > 0u) {
            count++;
            if (count >= timeout_cycles) {
                return -1;
            }
        }
    }
    return 0;
}

void sci_init(void)
{
    /* Step 1: Enable VCLK clock */
    (void)clock_enable(CLOCKREF_VCLK);

    /* Step 2: Apply x-ext.init sequence */

    /* [prov] regs.yaml:SCI.SCIGCR0 */
    SCIGCR0 |= 0x00000001u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    SCIGCR1 &= ~0x00000080u;

    /* [prov] regs.yaml:SCI.SCIPIO0 */
    SCIPIO0 |= 0x00000006u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    SCIGCR1 |= 0x01000000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    SCIGCR1 |= 0x00020000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    SCIGCR1 |= 0x03000000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    SCIGCR1 |= 0x00000080u;
}

void sci_set_baud_raw(uint32_t u, uint32_t m, uint32_t p)
{
    uint32_t val;
    /* [prov] regs.yaml:SCI.BRS */
    val = ((u & 0x7u) << 28) | ((m & 0xFu) << 24) | (p & 0xFFFFFFu);
    BRS = val;
}

int sci_set_baud(uint32_t target_baud, uint32_t vclk_hz)
{
    uint32_t u, m, p;
    uint32_t divisor;
    uint32_t best_u, best_m, best_p;
    uint32_t computed_baud;
    uint32_t error, best_error;
    uint32_t temp;

    if (target_baud == 0u || vclk_hz == 0u) {
        return -1;
    }

    best_error = 0xFFFFFFFFu;
    best_u = 0u;
    best_m = 0u;
    best_p = 0u;

    /* Baud = VCLK / ((M+1) * P * 2^U) */
    /* Try all U from 0..7, M from 0..15, compute P */
    for (u = 0u; u <= 7u; u++) {
        for (m = 0u; m <= 15u; m++) {
            divisor = (m + 1u) * (1u << u);
            if (divisor == 0u) {
                continue;
            }
            p = vclk_hz / (divisor * target_baud);
            if (p == 0u || p > 0xFFFFFFu) {
                continue;
            }
            computed_baud = vclk_hz / (divisor * p);
            if (computed_baud > target_baud) {
                error = computed_baud - target_baud;
            } else {
                error = target_baud - computed_baud;
            }
            if (error < best_error) {
                best_error = error;
                best_u = u;
                best_m = m;
                best_p = p;
            }
        }
    }

    if (best_p == 0u) {
        return -1;
    }

    sci_set_baud_raw(best_u, best_m, best_p);
    return 0;
}

void sci_set_format(uint32_t char_len, uint32_t stop_bits, uint32_t parity_enable, uint32_t parity_odd)
{
    uint32_t val;
    uint32_t gcr1;

    /* [prov] regs.yaml:SCI.SCIFORMAT */
    val = ((char_len & 0x7u) << 0) | ((char_len & 0x7u) << 16);
    SCIFORMAT = val;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    gcr1 = SCIGCR1;
    if (stop_bits != 0u) {
        gcr1 |= (1u << 4);
    } else {
        gcr1 &= ~(1u << 4);
    }
    if (parity_enable != 0u) {
        gcr1 |= (1u << 2);
        if (parity_odd != 0u) {
            gcr1 |= (1u << 3);
        } else {
            gcr1 &= ~(1u << 3);
        }
    } else {
        gcr1 &= ~(1u << 2);
    }
    SCIGCR1 = gcr1;
}

uint32_t sci_get_flags(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return SCIFLR;
}

void sci_clear_flags(uint32_t flags)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    SCIFLR = flags;
}

int sci_tx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (SCIFLR & (1u << 8)) != 0u ? 1 : 0;
}

int sci_rx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (SCIFLR & (1u << 9)) != 0u ? 1 : 0;
}

void sci_write_byte(uint8_t data)
{
    /* [prov] regs.yaml:SCI.SCITD */
    SCITD = (uint32_t)data;
}

uint8_t sci_read_byte(void)
{
    /* [prov] regs.yaml:SCI.SCIRD */
    return (uint8_t)(SCIRD & 0xFFu);
}

int sci_transmit_byte(uint8_t data, uint32_t timeout_cycles)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    if (sci_wait_for_flag((1u << 8), timeout_cycles) != 0) {
        return -1;
    }
    /* [prov] regs.yaml:SCI.SCITD */
    sci_write_byte(data);
    return 0;
}

int sci_receive_byte(uint8_t *data, uint32_t timeout_cycles)
{
    uint32_t flags;
    /* [prov] regs.yaml:SCI.SCIFLR */
    if (sci_wait_for_flag((1u << 9), timeout_cycles) != 0) {
        return -1;
    }
    flags = SCIFLR;
    /* Check error flags */
    if ((flags & ((1u << 24) | (1u << 25) | (1u << 26))) != 0u) {
        /* Clear error flags */
        sci_clear_flags((1u << 24) | (1u << 25) | (1u << 26));
        return -2;
    }
    /* [prov] regs.yaml:SCI.SCIRD */
    *data = sci_read_byte();
    return 0;
}

int sci_transmit(const uint8_t *buf, uint32_t len, uint32_t timeout_cycles)
{
    uint32_t i;
    int ret;
    for (i = 0u; i < len; i++) {
        ret = sci_transmit_byte(buf[i], timeout_cycles);
        if (ret != 0) {
            return (int)i;
        }
    }
    return (int)len;
}

int sci_receive(uint8_t *buf, uint32_t len, uint32_t timeout_cycles)
{
    uint32_t i;
    int ret;
    for (i = 0u; i < len; i++) {
        ret = sci_receive_byte(&buf[i], timeout_cycles);
        if (ret != 0) {
            return (int)i;
        }
    }
    return (int)len;
}

void sci_set_loopback(uint32_t enable)
{
    uint32_t gcr1;
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    gcr1 = SCIGCR1;
    if (enable != 0u) {
        gcr1 |= (1u << 16);
    } else {
        gcr1 &= ~(1u << 16);
    }
    SCIGCR1 = gcr1;
}

void sci_set_iodft_loopback(uint32_t enable)
{
    uint32_t val;
    /* [prov] regs.yaml:SCI.IODFTCTRL */
    val = IODFTCTRL;
    if (enable != 0u) {
        val |= (0xAu << 8);
        val |= (1u << 1);
    } else {
        val &= ~(1u << 1);
    }
    IODFTCTRL = val;
}

int sci_loopback_test(uint8_t test_byte, uint32_t timeout_cycles)
{
    uint8_t rx_byte;
    int ret;
    uint32_t original_gcr1;

    /* Save original loopback state */
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    original_gcr1 = SCIGCR1;

    /* Enable loopback */
    sci_set_loopback(1u);

    /* Transmit test byte */
    ret = sci_transmit_byte(test_byte, timeout_cycles);
    if (ret != 0) {
        /* Restore loopback state */
        SCIGCR1 = original_gcr1;
        return -1;
    }

    /* Receive byte */
    ret = sci_receive_byte(&rx_byte, timeout_cycles);
    if (ret != 0) {
        SCIGCR1 = original_gcr1;
        return -1;
    }

    /* Restore loopback state */
    SCIGCR1 = original_gcr1;

    /* Verify */
    if (rx_byte != test_byte) {
        return -1;
    }

    return 0;
}

int sci_register_isr(uint32_t channel_id, sci_isr_t isr)
{
    return vim_register_isr(channel_id, isr);
}

int sci_enable_irq(uint32_t channel_id)
{
    return vim_enable_channel(channel_id);
}

int sci_disable_irq(uint32_t channel_id)
{
    return vim_disable_channel(channel_id);
}

void sci_enable_interrupts(uint32_t int_mask)
{
    /* [prov] regs.yaml:SCI.SCISETINT */
    SCISETINT = int_mask;
}

void sci_disable_interrupts(uint32_t int_mask)
{
    /* [prov] regs.yaml:SCI.SCICLEARINT */
    SCICLEARINT = int_mask;
}

void sci_set_interrupt_level(uint32_t int_mask)
{
    /* [prov] regs.yaml:SCI.SCISETINTLVL */
    SCISETINTLVL = int_mask;
}

void sci_clear_interrupt_level(uint32_t int_mask)
{
    /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
    SCICLEARINTLVL = int_mask;
}