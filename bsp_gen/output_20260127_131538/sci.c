/**
 * @file sci.c
 * @brief Implementation of SCI/LIN driver for TI RM46
 */

#include <stdint.h>
#include "sci.h"
#include "clock.h"

/* VIM API declarations (provided by system-level code) */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* SCI base address and register offsets */
#define SCI_BASE                      (0xFFF7E400u)
#define SCI_SCIGCR0                   (SCI_BASE + 0x00u)
#define SCI_SCIGCR1                   (SCI_BASE + 0x04u)
#define SCI_SCIGCR2                   (SCI_BASE + 0x08u)
#define SCI_SCISETINT                 (SCI_BASE + 0x0Cu)
#define SCI_SCICLEARINT               (SCI_BASE + 0x10u)
#define SCI_SCISETINTLVL              (SCI_BASE + 0x14u)
#define SCI_SCICLEARINTLVL            (SCI_BASE + 0x18u)
#define SCI_SCIFLR                    (SCI_BASE + 0x1Cu)
#define SCI_SCIINTVECT0               (SCI_BASE + 0x20u)
#define SCI_SCIINTVECT1               (SCI_BASE + 0x24u)
#define SCI_SCIFORMAT                 (SCI_BASE + 0x28u)
#define SCI_BRS                       (SCI_BASE + 0x2Cu)
#define SCI_SCIRD                     (SCI_BASE + 0x34u)
#define SCI_SCITD                     (SCI_BASE + 0x38u)
#define SCI_SCIPIO0                   (SCI_BASE + 0x3Cu)
#define SCI_IODFTCTRL                 (SCI_BASE + 0x90u)

/* Bit positions and masks */
#define SCIGCR0_RESET                 (1u << 0)
#define SCIGCR1_TXENA                 (1u << 25)
#define SCIGCR1_RXENA                 (1u << 24)
#define SCIGCR1_LOOP_BACK             (1u << 16)
#define SCIGCR1_SWnRST                (1u << 7)
#define SCIGCR1_PARITY_ENA            (1u << 2)
#define SCIGCR1_PARITY                (1u << 3)
#define SCIGCR1_STOP                  (1u << 4)

#define SCIFLR_TXRDY                  (1u << 8)
#define SCIFLR_RXRDY                  (1u << 9)
#define SCIFLR_TX_EMPTY               (1u << 11)
#define SCIFLR_PE                     (1u << 24)
#define SCIFLR_OE                     (1u << 25)
#define SCIFLR_FE                     (1u << 26)

#define SCISETINT_SET_RX_INT          (1u << 9)
#define SCISETINT_SET_TX_INT          (1u << 8)

#define SCICLEARINT_CLR_RX_INT        (1u << 9)
#define SCICLEARINT_CLR_TX_INT        (1u << 8)

#define SCIPIO0_TX_FUNC               (1u << 2)
#define SCIPIO0_RX_FUNC               (1u << 1)

#define IODFTCTRL_LPB_ENA             (1u << 1)
#define IODFTCTRL_IODFTENA_KEY        (0xAu)

/* Timeout for blocking operations (iterations) */
#define SCI_TIMEOUT                   (100000u)

/* Internal helper: wait for a flag with timeout */
static int sci_wait_flag(uint32_t flag_mask, uint32_t timeout)
{
    uint32_t i;
    for (i = 0; i < timeout; ++i) {
        /* [prov] regs.yaml:SCI.SCIFLR */
        if (REG32(SCI_SCIFLR) & flag_mask) {
            return 0;
        }
    }
    return -1;
}

void sci_init(void)
{
    uint32_t tmp;

    /* Enable VCLK clock for SCI */
    clock_enable(CLOCKREF_VCLK);

    /* Apply init sequence from x-ext.init */

    /* [prov] regs.yaml:SCI.SCIGCR0 */
    /* Set SCIGCR0.RESET = 1 (bring out of reset) */
    REG32(SCI_SCIGCR0) |= 0x00000001u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Clear SCIGCR1 bit 7 (SWnRST = 0, module in reset state) */
    tmp = REG32(SCI_SCIGCR1);
    tmp &= ~0x00000080u;
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.SCIPIO0 */
    /* Set SCIPIO0 TX_FUNC and RX_FUNC */
    REG32(SCI_SCIPIO0) |= 0x00000006u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set TXENA (bit 25) */
    REG32(SCI_SCIGCR1) |= 0x01000000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set RXENA (bit 24) via CONT bit (bit 17) */
    REG32(SCI_SCIGCR1) |= 0x00020000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set both TXENA and RXENA again (0x03000000) */
    REG32(SCI_SCIGCR1) |= 0x03000000u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set SWnRST = 1 (release from reset) */
    REG32(SCI_SCIGCR1) |= 0x00000080u;
}

void sci_configure(uint8_t char_length, sci_parity_t parity, uint8_t stop_bits)
{
    uint32_t gcr1;
    uint32_t format;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    gcr1 = REG32(SCI_SCIGCR1);

    /* Configure parity */
    if (parity == SCI_PARITY_NONE) {
        gcr1 &= ~SCIGCR1_PARITY_ENA;
    } else {
        gcr1 |= SCIGCR1_PARITY_ENA;
        if (parity == SCI_PARITY_ODD) {
            gcr1 |= SCIGCR1_PARITY;
        } else {
            gcr1 &= ~SCIGCR1_PARITY;
        }
    }

    /* Configure stop bits */
    if (stop_bits != 0) {
        gcr1 |= SCIGCR1_STOP;
    } else {
        gcr1 &= ~SCIGCR1_STOP;
    }

    REG32(SCI_SCIGCR1) = gcr1;

    /* [prov] regs.yaml:SCI.SCIFORMAT */
    /* Set character length (CHAR field, bits 2:0) */
    format = REG32(SCI_SCIFORMAT);
    format &= ~0x7u;
    format |= (char_length - 1u) & 0x7u;
    REG32(SCI_SCIFORMAT) = format;
}

int sci_set_baudrate(uint32_t baudrate)
{
    uint32_t vclk_hz;
    uint32_t p;
    uint32_t brs_val;

    if (baudrate == 0) {
        return -1;
    }

    /* Get VCLK frequency */
    vclk_hz = clock_get_hz(CLOCKREF_VCLK);
    if (vclk_hz == 0) {
        return -1;
    }

    /* Compute prescaler P: P = (VCLK / (16 * baudrate)) - 1 */
    p = (vclk_hz / (16u * baudrate));
    if (p > 0) {
        p -= 1u;
    }

    if (p > 0xFFFFFFu) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.BRS */
    /* Set BRS.PRESCALER_P (bits 23:0), M=0, U=0 */
    brs_val = p & 0xFFFFFFu;
    REG32(SCI_BRS) = brs_val;

    return 0;
}

int sci_putc(uint8_t byte)
{
    /* Wait for TXRDY */
    if (sci_wait_flag(SCIFLR_TXRDY, SCI_TIMEOUT) != 0) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCITD */
    REG32(SCI_SCITD) = byte;

    return 0;
}

int sci_getc(void)
{
    uint32_t flags;

    /* Wait for RXRDY */
    if (sci_wait_flag(SCIFLR_RXRDY, SCI_TIMEOUT) != 0) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCIFLR */
    flags = REG32(SCI_SCIFLR);

    /* Check for errors */
    if (flags & (SCIFLR_PE | SCIFLR_OE | SCIFLR_FE)) {
        /* Clear error flags */
        sci_clear_flags(SCIFLR_PE | SCIFLR_OE | SCIFLR_FE);
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCIRD */
    return (int)(REG32(SCI_SCIRD) & 0xFFu);
}

uint32_t sci_write(const uint8_t *buf, uint32_t len)
{
    uint32_t i;
    for (i = 0; i < len; ++i) {
        if (sci_putc(buf[i]) != 0) {
            break;
        }
    }
    return i;
}

uint32_t sci_read(uint8_t *buf, uint32_t len)
{
    uint32_t i;
    int ch;

    for (i = 0; i < len; ++i) {
        ch = sci_getc();
        if (ch < 0) {
            break;
        }
        buf[i] = (uint8_t)ch;
    }
    return i;
}

int sci_tx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCI_SCIFLR) & SCIFLR_TXRDY) ? 1 : 0;
}

int sci_rx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCI_SCIFLR) & SCIFLR_RXRDY) ? 1 : 0;
}

int sci_tx_empty(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCI_SCIFLR) & SCIFLR_TX_EMPTY) ? 1 : 0;
}

uint32_t sci_get_flags(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return REG32(SCI_SCIFLR);
}

void sci_clear_flags(uint32_t flags)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    /* Writing 1 clears RWC flags */
    REG32(SCI_SCIFLR) = flags;
}

void sci_enable_loopback(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCI_SCIGCR1) |= SCIGCR1_LOOP_BACK;

    /* [prov] regs.yaml:SCI.IODFTCTRL */
    /* Enable IODFT with key and loopback */
    REG32(SCI_IODFTCTRL) = (IODFTCTRL_IODFTENA_KEY << 8) | IODFTCTRL_LPB_ENA;
}

void sci_disable_loopback(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCI_SCIGCR1) &= ~SCIGCR1_LOOP_BACK;

    /* [prov] regs.yaml:SCI.IODFTCTRL */
    REG32(SCI_IODFTCTRL) = 0;
}

int sci_loopback_test(void)
{
    uint8_t test_pattern[4];
    uint8_t recv_buf[4];
    uint32_t i;

    test_pattern[0] = 0x55u;
    test_pattern[1] = 0xAAu;
    test_pattern[2] = 0xF0u;
    test_pattern[3] = 0x0Fu;

    sci_enable_loopback();

    /* Transmit test pattern */
    if (sci_write(test_pattern, 4) != 4) {
        sci_disable_loopback();
        return -1;
    }

    /* Receive and compare */
    if (sci_read(recv_buf, 4) != 4) {
        sci_disable_loopback();
        return -1;
    }

    for (i = 0; i < 4; ++i) {
        if (recv_buf[i] != test_pattern[i]) {
            sci_disable_loopback();
            return -1;
        }
    }

    sci_disable_loopback();
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

void sci_enable_rx_int(void)
{
    /* [prov] regs.yaml:SCI.SCISETINT */
    REG32(SCI_SCISETINT) = SCISETINT_SET_RX_INT;
}

void sci_disable_rx_int(void)
{
    /* [prov] regs.yaml:SCI.SCICLEARINT */
    REG32(SCI_SCICLEARINT) = SCICLEARINT_CLR_RX_INT;
}

void sci_enable_tx_int(void)
{
    /* [prov] regs.yaml:SCI.SCISETINT */
    REG32(SCI_SCISETINT) = SCISETINT_SET_TX_INT;
}

void sci_disable_tx_int(void)
{
    /* [prov] regs.yaml:SCI.SCICLEARINT */
    REG32(SCI_SCICLEARINT) = SCICLEARINT_CLR_TX_INT;
}

uint32_t sci_get_intvect0(void)
{
    /* [prov] regs.yaml:SCI.SCIINTVECT0 */
    return REG32(SCI_SCIINTVECT0) & 0x1Fu;
}

uint32_t sci_get_intvect1(void)
{
    /* [prov] regs.yaml:SCI.SCIINTVECT1 */
    return REG32(SCI_SCIINTVECT1) & 0x1Fu;
}