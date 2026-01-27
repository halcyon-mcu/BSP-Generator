/**
 * @file sci.c
 * @brief SCI/LIN driver implementation for TI RM46
 */

#include <stdint.h>
#include "sci.h"
#include "clock.h"

/* External VIM API (provided by system-level driver) */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* SCI base and register offsets from FACTS MIRROR */
#define SCI_BASE                    (0xFFF7E400u)
#define SCI_SCIGCR0                 (SCI_BASE + 0x00u)
#define SCI_SCIGCR1                 (SCI_BASE + 0x04u)
#define SCI_SCIGCR2                 (SCI_BASE + 0x08u)
#define SCI_SCISETINT               (SCI_BASE + 0x0Cu)
#define SCI_SCICLEARINT             (SCI_BASE + 0x10u)
#define SCI_SCISETINTLVL            (SCI_BASE + 0x14u)
#define SCI_SCICLEARINTLVL          (SCI_BASE + 0x18u)
#define SCI_SCIFLR                  (SCI_BASE + 0x1Cu)
#define SCI_SCIINTVECT0             (SCI_BASE + 0x20u)
#define SCI_SCIINTVECT1             (SCI_BASE + 0x24u)
#define SCI_SCIFORMAT               (SCI_BASE + 0x28u)
#define SCI_BRS                     (SCI_BASE + 0x2Cu)
#define SCI_SCIRD                   (SCI_BASE + 0x34u)
#define SCI_SCITD                   (SCI_BASE + 0x38u)
#define SCI_SCIPIO0                 (SCI_BASE + 0x3Cu)
#define SCI_IODFTCTRL               (SCI_BASE + 0x90u)

/* Bit positions and masks from FACTS MIRROR */
#define SCIGCR0_RESET_BIT           (0u)
#define SCIGCR1_TXENA_BIT           (25u)
#define SCIGCR1_RXENA_BIT           (24u)
#define SCIGCR1_CONT_BIT            (17u)
#define SCIGCR1_LOOP_BACK_BIT       (16u)
#define SCIGCR1_SWnRST_BIT          (7u)
#define SCIGCR1_LIN_MODE_BIT        (6u)
#define SCIGCR1_CLOCK_BIT           (5u)
#define SCIGCR1_STOP_BIT            (4u)
#define SCIGCR1_PARITY_BIT          (3u)
#define SCIGCR1_PARITY_ENA_BIT      (2u)
#define SCIGCR2_POWERDOWN_BIT       (0u)
#define SCISETINT_SET_RX_INT_BIT    (9u)
#define SCISETINT_SET_TX_INT_BIT    (8u)
#define SCICLEARINT_CLR_RX_INT_BIT  (9u)
#define SCICLEARINT_CLR_TX_INT_BIT  (8u)
#define SCISETINTLVL_SET_RX_INT_LVL_BIT (9u)
#define SCISETINTLVL_SET_TX_INT_LVL_BIT (8u)
#define SCICLEARINTLVL_CLR_RX_INT_LVL_BIT (9u)
#define SCICLEARINTLVL_CLR_TX_INT_LVL_BIT (8u)
#define SCIFLR_FE_BIT               (26u)
#define SCIFLR_OE_BIT               (25u)
#define SCIFLR_PE_BIT               (24u)
#define SCIFLR_TX_EMPTY_BIT         (11u)
#define SCIFLR_RXRDY_BIT            (9u)
#define SCIFLR_TXRDY_BIT            (8u)
#define SCIFLR_BUSY_BIT             (3u)
#define SCIPIO0_TX_FUNC_BIT         (2u)
#define SCIPIO0_RX_FUNC_BIT         (1u)
#define IODFTCTRL_LPB_ENA_BIT       (1u)
#define IODFTCTRL_RXP_ENA_BIT       (0u)
#define IODFTCTRL_IODFTENA_SHIFT    (8u)
#define IODFTCTRL_IODFTENA_KEY      (0x0Au)

/* Init sequence values from FACTS MIRROR */
#define INIT_SCIGCR0_SET_VALUE      (0x00000001u)
#define INIT_SCIGCR1_CLEAR_VALUE    (0x00000080u)
#define INIT_SCIPIO0_SET_VALUE      (0x00000006u)
#define INIT_SCIGCR1_SET_VALUE_1    (0x01000000u)
#define INIT_SCIGCR1_SET_VALUE_2    (0x00020000u)
#define INIT_SCIGCR1_SET_VALUE_3    (0x03000000u)
#define INIT_SCIGCR1_SET_VALUE_4    (0x00000080u)

/* IRQ channel IDs from FACTS MIRROR */
#define IRQ_SCI_LVL0                (64u)
#define IRQ_SCI_LVL1                (74u)

void sci_init(void)
{
    uint32_t tmp;

    /* Enable VCLK clock for SCI */
    (void)clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:SCI.SCIGCR0 */
    /* Bring SCI out of reset */
    tmp = REG32(SCI_SCIGCR0);
    tmp |= INIT_SCIGCR0_SET_VALUE;
    REG32(SCI_SCIGCR0) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Clear SWnRST to enter config mode */
    tmp = REG32(SCI_SCIGCR1);
    tmp &= ~INIT_SCIGCR1_CLEAR_VALUE;
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.SCIPIO0 */
    /* Configure TX and RX pin functions */
    tmp = REG32(SCI_SCIPIO0);
    tmp |= INIT_SCIPIO0_SET_VALUE;
    REG32(SCI_SCIPIO0) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set TXENA */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= INIT_SCIGCR1_SET_VALUE_1;
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set CONT */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= INIT_SCIGCR1_SET_VALUE_2;
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set TXENA and RXENA */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= INIT_SCIGCR1_SET_VALUE_3;
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set SWnRST to bring module out of reset */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= INIT_SCIGCR1_SET_VALUE_4;
    REG32(SCI_SCIGCR1) = tmp;
}

void sci_configure_baud(uint32_t baud_rate)
{
    uint32_t vclk_hz;
    uint32_t p;
    uint32_t tmp;

    vclk_hz = clock_get_hz(CLOCKREF_VCLK);

    /* Compute prescaler P = (VCLK / (16 * baud)) - 1 */
    p = (vclk_hz / (16u * baud_rate)) - 1u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Clear SWnRST */
    tmp = REG32(SCI_SCIGCR1);
    tmp &= ~(1u << SCIGCR1_SWnRST_BIT);
    REG32(SCI_SCIGCR1) = tmp;

    /* [prov] regs.yaml:SCI.BRS */
    /* Write prescaler to BRS.PRESCALER_P [23:0] */
    tmp = REG32(SCI_BRS);
    tmp &= 0xFF000000u; /* Clear P field */
    tmp |= (p & 0x00FFFFFFu);
    REG32(SCI_BRS) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Set SWnRST */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= (1u << SCIGCR1_SWnRST_BIT);
    REG32(SCI_SCIGCR1) = tmp;
}

int sci_configure_frame(const sci_frame_config_t *config)
{
    uint32_t tmp;

    if (config == (void *)0) {
        return -1;
    }

    if (config->char_length == 0u || config->char_length > 8u) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCIFORMAT */
    /* Set CHAR field [2:0] = (char_length - 1) */
    tmp = REG32(SCI_SCIFORMAT);
    tmp &= ~(0x07u); /* Clear CHAR bits [2:0] */
    tmp |= ((config->char_length - 1u) & 0x07u);
    REG32(SCI_SCIFORMAT) = tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Configure STOP, PARITY, PARITY_ENA */
    tmp = REG32(SCI_SCIGCR1);
    if (config->stop_bits != 0u) {
        tmp |= (1u << SCIGCR1_STOP_BIT);
    } else {
        tmp &= ~(1u << SCIGCR1_STOP_BIT);
    }
    if (config->parity_en != 0u) {
        tmp |= (1u << SCIGCR1_PARITY_ENA_BIT);
        if (config->parity_odd != 0u) {
            tmp |= (1u << SCIGCR1_PARITY_BIT);
        } else {
            tmp &= ~(1u << SCIGCR1_PARITY_BIT);
        }
    } else {
        tmp &= ~(1u << SCIGCR1_PARITY_ENA_BIT);
    }
    REG32(SCI_SCIGCR1) = tmp;

    return 0;
}

static int sci_wait_flag(uint32_t bit, uint32_t timeout_cycles)
{
    uint32_t i;
    uint32_t flags;

    for (i = 0u; i < timeout_cycles; ++i) {
        /* [prov] regs.yaml:SCI.SCIFLR */
        flags = REG32(SCI_SCIFLR);
        if ((flags & (1u << bit)) != 0u) {
            return 0;
        }
    }
    return (int)SCI_ERR_TIMEOUT;
}

int sci_transmit_byte(uint8_t data, uint32_t timeout_cycles)
{
    int ret;
    uint32_t tmp;

    /* Wait for TXRDY */
    ret = sci_wait_flag(SCIFLR_TXRDY_BIT, timeout_cycles);
    if (ret != 0) {
        return ret;
    }

    /* [prov] regs.yaml:SCI.SCITD */
    /* Write data to transmit buffer */
    tmp = REG32(SCI_SCITD);
    tmp &= 0xFFFFFF00u;
    tmp |= (uint32_t)data;
    REG32(SCI_SCITD) = tmp;

    /* Wait for TX_EMPTY */
    ret = sci_wait_flag(SCIFLR_TX_EMPTY_BIT, timeout_cycles);
    return ret;
}

int sci_receive_byte(uint8_t *data, uint32_t timeout_cycles)
{
    int ret;
    uint32_t flags;
    int errors;

    if (data == (void *)0) {
        return (int)SCI_ERR_TIMEOUT;
    }

    /* Wait for RXRDY */
    ret = sci_wait_flag(SCIFLR_RXRDY_BIT, timeout_cycles);
    if (ret != 0) {
        return ret;
    }

    /* [prov] regs.yaml:SCI.SCIFLR */
    /* Check for errors */
    flags = REG32(SCI_SCIFLR);
    errors = (int)SCI_ERR_NONE;

    if ((flags & (1u << SCIFLR_FE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_FRAMING;
        /* Clear FE flag */
        REG32(SCI_SCIFLR) = (1u << SCIFLR_FE_BIT);
    }
    if ((flags & (1u << SCIFLR_OE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_OVERRUN;
        /* Clear OE flag */
        REG32(SCI_SCIFLR) = (1u << SCIFLR_OE_BIT);
    }
    if ((flags & (1u << SCIFLR_PE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_PARITY;
        /* Clear PE flag */
        REG32(SCI_SCIFLR) = (1u << SCIFLR_PE_BIT);
    }

    /* [prov] regs.yaml:SCI.SCIRD */
    /* Read received byte */
    *data = (uint8_t)(REG32(SCI_SCIRD) & 0xFFu);

    return errors;
}

void sci_enable_loopback(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    tmp = REG32(SCI_SCIGCR1);
    tmp |= (1u << SCIGCR1_LOOP_BACK_BIT);
    REG32(SCI_SCIGCR1) = tmp;
}

void sci_disable_loopback(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    tmp = REG32(SCI_SCIGCR1);
    tmp &= ~(1u << SCIGCR1_LOOP_BACK_BIT);
    REG32(SCI_SCIGCR1) = tmp;
}

void sci_enable_analog_loopback(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.IODFTCTRL */
    /* Set IODFTENA key and enable RXP_ENA */
    tmp = REG32(SCI_IODFTCTRL);
    tmp &= ~(0x0Fu << IODFTCTRL_IODFTENA_SHIFT);
    tmp |= (IODFTCTRL_IODFTENA_KEY << IODFTCTRL_IODFTENA_SHIFT);
    tmp |= (1u << IODFTCTRL_RXP_ENA_BIT);
    REG32(SCI_IODFTCTRL) = tmp;
}

void sci_disable_analog_loopback(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.IODFTCTRL */
    tmp = REG32(SCI_IODFTCTRL);
    tmp &= ~(1u << IODFTCTRL_RXP_ENA_BIT);
    REG32(SCI_IODFTCTRL) = tmp;
}

int sci_self_test(void)
{
    uint8_t tx_byte;
    uint8_t rx_byte;
    int ret;
    uint32_t saved_gcr1;

    tx_byte = 0x55u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Save current GCR1 */
    saved_gcr1 = REG32(SCI_SCIGCR1);

    /* Enter reset to enable loopback */
    REG32(SCI_SCIGCR1) = saved_gcr1 & ~(1u << SCIGCR1_SWnRST_BIT);

    /* Enable loopback */
    sci_enable_loopback();

    /* Exit reset */
    REG32(SCI_SCIGCR1) = saved_gcr1 | (1u << SCIGCR1_LOOP_BACK_BIT);

    /* Transmit test byte */
    ret = sci_transmit_byte(tx_byte, 10000u);
    if (ret != 0) {
        sci_disable_loopback();
        REG32(SCI_SCIGCR1) = saved_gcr1;
        return -1;
    }

    /* Receive test byte */
    ret = sci_receive_byte(&rx_byte, 10000u);
    if (ret != (int)SCI_ERR_NONE) {
        sci_disable_loopback();
        REG32(SCI_SCIGCR1) = saved_gcr1;
        return -2;
    }

    /* Verify */
    if (rx_byte != tx_byte) {
        sci_disable_loopback();
        REG32(SCI_SCIGCR1) = saved_gcr1;
        return -3;
    }

    /* Restore original state */
    sci_disable_loopback();
    REG32(SCI_SCIGCR1) = saved_gcr1;

    return 0;
}

int sci_register_isr_lvl0(sci_isr_t isr)
{
    return vim_register_isr(IRQ_SCI_LVL0, isr);
}

int sci_register_isr_lvl1(sci_isr_t isr)
{
    return vim_register_isr(IRQ_SCI_LVL1, isr);
}

int sci_enable_irq_lvl0(void)
{
    return vim_enable_channel(IRQ_SCI_LVL0);
}

int sci_enable_irq_lvl1(void)
{
    return vim_enable_channel(IRQ_SCI_LVL1);
}

int sci_disable_irq_lvl0(void)
{
    return vim_disable_channel(IRQ_SCI_LVL0);
}

int sci_disable_irq_lvl1(void)
{
    return vim_disable_channel(IRQ_SCI_LVL1);
}

void sci_enable_rx_interrupt_lvl0(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
    /* Clear RX interrupt level (route to level 0) */
    tmp = (1u << SCICLEARINTLVL_CLR_RX_INT_LVL_BIT);
    REG32(SCI_SCICLEARINTLVL) = tmp;

    /* [prov] regs.yaml:SCI.SCISETINT */
    /* Enable RX interrupt */
    tmp = (1u << SCISETINT_SET_RX_INT_BIT);
    REG32(SCI_SCISETINT) = tmp;
}

void sci_enable_tx_interrupt_lvl0(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
    /* Clear TX interrupt level (route to level 0) */
    tmp = (1u << SCICLEARINTLVL_CLR_TX_INT_LVL_BIT);
    REG32(SCI_SCICLEARINTLVL) = tmp;

    /* [prov] regs.yaml:SCI.SCISETINT */
    /* Enable TX interrupt */
    tmp = (1u << SCISETINT_SET_TX_INT_BIT);
    REG32(SCI_SCISETINT) = tmp;
}

void sci_enable_rx_interrupt_lvl1(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCISETINTLVL */
    /* Set RX interrupt level to level 1 */
    tmp = (1u << SCISETINTLVL_SET_RX_INT_LVL_BIT);
    REG32(SCI_SCISETINTLVL) = tmp;

    /* [prov] regs.yaml:SCI.SCISETINT */
    /* Enable RX interrupt */
    tmp = (1u << SCISETINT_SET_RX_INT_BIT);
    REG32(SCI_SCISETINT) = tmp;
}

void sci_enable_tx_interrupt_lvl1(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCISETINTLVL */
    /* Set TX interrupt level to level 1 */
    tmp = (1u << SCISETINTLVL_SET_TX_INT_LVL_BIT);
    REG32(SCI_SCISETINTLVL) = tmp;

    /* [prov] regs.yaml:SCI.SCISETINT */
    /* Enable TX interrupt */
    tmp = (1u << SCISETINT_SET_TX_INT_BIT);
    REG32(SCI_SCISETINT) = tmp;
}

void sci_disable_rx_interrupt(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINT */
    /* Clear RX interrupt enable */
    tmp = (1u << SCICLEARINT_CLR_RX_INT_BIT);
    REG32(SCI_SCICLEARINT) = tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
    /* Clear RX interrupt level */
    tmp = (1u << SCICLEARINTLVL_CLR_RX_INT_LVL_BIT);
    REG32(SCI_SCICLEARINTLVL) = tmp;
}

void sci_disable_tx_interrupt(void)
{
    uint32_t tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINT */
    /* Clear TX interrupt enable */
    tmp = (1u << SCICLEARINT_CLR_TX_INT_BIT);
    REG32(SCI_SCICLEARINT) = tmp;

    /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
    /* Clear TX interrupt level */
    tmp = (1u << SCICLEARINTLVL_CLR_TX_INT_LVL_BIT);
    REG32(SCI_SCICLEARINTLVL) = tmp;
}

int sci_is_rx_ready(void)
{
    uint32_t flags;

    /* [prov] regs.yaml:SCI.SCIFLR */
    flags = REG32(SCI_SCIFLR);
    return ((flags & (1u << SCIFLR_RXRDY_BIT)) != 0u) ? 1 : 0;
}

int sci_is_tx_ready(void)
{
    uint32_t flags;

    /* [prov] regs.yaml:SCI.SCIFLR */
    flags = REG32(SCI_SCIFLR);
    return ((flags & (1u << SCIFLR_TXRDY_BIT)) != 0u) ? 1 : 0;
}

int sci_is_tx_empty(void)
{
    uint32_t flags;

    /* [prov] regs.yaml:SCI.SCIFLR */
    flags = REG32(SCI_SCIFLR);
    return ((flags & (1u << SCIFLR_TX_EMPTY_BIT)) != 0u) ? 1 : 0;
}

int sci_get_and_clear_errors(void)
{
    uint32_t flags;
    int errors;

    /* [prov] regs.yaml:SCI.SCIFLR */
    flags = REG32(SCI_SCIFLR);

    errors = (int)SCI_ERR_NONE;

    if ((flags & (1u << SCIFLR_FE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_FRAMING;
        REG32(SCI_SCIFLR) = (1u << SCIFLR_FE_BIT);
    }
    if ((flags & (1u << SCIFLR_OE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_OVERRUN;
        REG32(SCI_SCIFLR) = (1u << SCIFLR_OE_BIT);
    }
    if ((flags & (1u << SCIFLR_PE_BIT)) != 0u) {
        errors |= (int)SCI_ERR_PARITY;
        REG32(SCI_SCIFLR) = (1u << SCIFLR_PE_BIT);
    }

    return errors;
}