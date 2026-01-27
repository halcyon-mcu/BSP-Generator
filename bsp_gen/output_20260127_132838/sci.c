#include <stdint.h>
#include "sci.h"
#include "clock.h"

/* External VIM API prototypes */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Register access helper */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* Base address from FACTS MIRROR */
#define SCI_BASE (0xFFF7E400u)

/* Register offsets from FACTS MIRROR */
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
#define SCIRD_OFFSET     (0x34u)
#define SCITD_OFFSET     (0x38u)
#define SCIPIO0_OFFSET   (0x3Cu)
#define IODFTCTRL_OFFSET (0x90u)

/* Register addresses */
#define SCIGCR0   (SCI_BASE + SCIGCR0_OFFSET)
#define SCIGCR1   (SCI_BASE + SCIGCR1_OFFSET)
#define SCIGCR2   (SCI_BASE + SCIGCR2_OFFSET)
#define SCISETINT (SCI_BASE + SCISETINT_OFFSET)
#define SCICLEARINT (SCI_BASE + SCICLEARINT_OFFSET)
#define SCISETINTLVL (SCI_BASE + SCISETINTLVL_OFFSET)
#define SCICLEARINTLVL (SCI_BASE + SCICLEARINTLVL_OFFSET)
#define SCIFLR    (SCI_BASE + SCIFLR_OFFSET)
#define SCIFORMAT (SCI_BASE + SCIFORMAT_OFFSET)
#define BRS       (SCI_BASE + BRS_OFFSET)
#define SCIRD     (SCI_BASE + SCIRD_OFFSET)
#define SCITD     (SCI_BASE + SCITD_OFFSET)
#define SCIPIO0   (SCI_BASE + SCIPIO0_OFFSET)
#define IODFTCTRL (SCI_BASE + IODFTCTRL_OFFSET)

/* Bit positions from FACTS MIRROR */
#define SCIGCR0_RESET_BIT     (0u)
#define SCIGCR1_TXENA_BIT     (25u)
#define SCIGCR1_RXENA_BIT     (24u)
#define SCIGCR1_LOOP_BACK_BIT (16u)
#define SCIGCR1_SWnRST_BIT    (7u)
#define SCIGCR1_STOP_BIT      (4u)
#define SCIGCR1_PARITY_BIT    (3u)
#define SCIGCR1_PARITY_ENA_BIT (2u)

#define SCIFLR_TXRDY_BIT      (8u)
#define SCIFLR_RXRDY_BIT      (9u)
#define SCIFLR_TX_EMPTY_BIT   (11u)
#define SCIFLR_BUSY_BIT       (3u)
#define SCIFLR_PE_BIT         (24u)
#define SCIFLR_OE_BIT         (25u)
#define SCIFLR_FE_BIT         (26u)

#define SCISETINT_SET_RX_INT_BIT (9u)
#define SCISETINT_SET_TX_INT_BIT (8u)

#define SCISETINTLVL_SET_RX_INT_LVL_BIT (9u)
#define SCISETINTLVL_SET_TX_INT_LVL_BIT (8u)

#define SCICLEARINT_CLR_RX_INT_BIT (9u)
#define SCICLEARINT_CLR_TX_INT_BIT (8u)

#define SCICLEARINTLVL_CLR_RX_INT_LVL_BIT (9u)
#define SCICLEARINTLVL_CLR_TX_INT_LVL_BIT (8u)

#define SCIPIO0_TX_FUNC_BIT   (2u)
#define SCIPIO0_RX_FUNC_BIT   (1u)

#define IODFTCTRL_LPB_ENA_BIT (1u)

#define SCIFORMAT_CHAR_LSB    (0u)
#define SCIFORMAT_CHAR_MSB    (2u)

#define BRS_PRESCALER_P_LSB   (0u)
#define BRS_PRESCALER_P_MSB   (23u)
#define BRS_M_LSB             (24u)
#define BRS_M_MSB             (27u)

#define SCIRD_RD_LSB          (0u)
#define SCIRD_RD_MSB          (7u)

#define SCITD_TD_LSB          (0u)
#define SCITD_TD_MSB          (7u)

/* Init constants from FACTS MIRROR */
#define SCIGCR0_INIT_VALUE    (0x00000001u)
#define SCIGCR1_INIT_CLR_VALUE (0x00000080u)
#define SCIPIO0_INIT_SET_VALUE (0x00000006u)
#define SCIGCR1_INIT_SET1_VALUE (0x01000000u)
#define SCIGCR1_INIT_SET2_VALUE (0x00020000u)
#define SCIGCR1_INIT_SET3_VALUE (0x03000000u)
#define SCIGCR1_INIT_SET4_VALUE (0x00000080u)

/* Interrupt IDs from FACTS MIRROR */
#define IRQ_SCI_LVL0_ID (64u)
#define IRQ_SCI_LVL1_ID (74u)

/* Timeout constant */
#define SCI_TIMEOUT (100000u)

/* Helper: wait for a flag bit to be set, with timeout */
static int sci_wait_flag(uint32_t flag_bit, uint32_t timeout)
{
    uint32_t i;
    for (i = 0; i < timeout; i++) {
        /* [prov] regs.yaml:SCI.SCIFLR */
        if (REG32(SCIFLR) & (1u << flag_bit)) {
            return 0;
        }
    }
    return -1;
}

void sci_init(void)
{
    /* Enable VCLK clock */
    clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:SCI.SCIGCR0 */
    /* Step 1: Set RESET bit to reset the module */
    REG32(SCIGCR0) = SCIGCR0_INIT_VALUE;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Step 2: Clear SWnRST bit (hold in reset) */
    REG32(SCIGCR1) &= ~SCIGCR1_INIT_CLR_VALUE;

    /* [prov] regs.yaml:SCI.SCIPIO0 */
    /* Step 3: Configure pin functions (TX_FUNC, RX_FUNC) */
    REG32(SCIPIO0) |= SCIPIO0_INIT_SET_VALUE;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Step 4: Set TXENA (enable transmitter) */
    REG32(SCIGCR1) |= SCIGCR1_INIT_SET1_VALUE;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Step 5: Set CONT (continue on suspend) */
    REG32(SCIGCR1) |= SCIGCR1_INIT_SET2_VALUE;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Step 6: Set TXENA and RXENA (enable transmitter and receiver) */
    REG32(SCIGCR1) |= SCIGCR1_INIT_SET3_VALUE;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    /* Step 7: Set SWnRST (bring out of reset) */
    REG32(SCIGCR1) |= SCIGCR1_INIT_SET4_VALUE;
}

void sci_configure_format(uint32_t char_length, sci_parity_t parity, sci_stop_bits_t stop_bits)
{
    uint32_t gcr1_val;
    uint32_t format_val;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    gcr1_val = REG32(SCIGCR1);

    /* Configure stop bits */
    if (stop_bits == SCI_STOP_BITS_2) {
        gcr1_val |= (1u << SCIGCR1_STOP_BIT);
    } else {
        gcr1_val &= ~(1u << SCIGCR1_STOP_BIT);
    }

    /* Configure parity */
    if (parity == SCI_PARITY_NONE) {
        gcr1_val &= ~(1u << SCIGCR1_PARITY_ENA_BIT);
    } else {
        gcr1_val |= (1u << SCIGCR1_PARITY_ENA_BIT);
        if (parity == SCI_PARITY_ODD) {
            gcr1_val |= (1u << SCIGCR1_PARITY_BIT);
        } else {
            gcr1_val &= ~(1u << SCIGCR1_PARITY_BIT);
        }
    }

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) = gcr1_val;

    /* [prov] regs.yaml:SCI.SCIFORMAT */
    /* Configure character length (bits 0..2) */
    format_val = REG32(SCIFORMAT);
    format_val &= ~(0x7u << SCIFORMAT_CHAR_LSB);
    format_val |= ((char_length - 1u) & 0x7u) << SCIFORMAT_CHAR_LSB;
    REG32(SCIFORMAT) = format_val;
}

void sci_set_baudrate(uint32_t baudrate)
{
    uint32_t vclk_hz;
    uint32_t p;
    uint32_t brs_val;

    vclk_hz = clock_get_hz(CLOCKREF_VCLK);

    /* Compute prescaler P for desired baud rate.
     * baud = VCLK / ((P+1) * 16)
     * => P = (VCLK / (baud * 16)) - 1
     * Simplified: P = (vclk_hz / (baudrate * 16)) - 1
     */
    p = (vclk_hz / (baudrate * 16u)) - 1u;

    /* [prov] regs.yaml:SCI.BRS */
    /* Write prescaler P to bits 0..23, M=0, U=0 for simplicity */
    brs_val = (p & 0x00FFFFFFu);
    REG32(BRS) = brs_val;
}

void sci_enable_tx(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) |= (1u << SCIGCR1_TXENA_BIT);
}

void sci_disable_tx(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) &= ~(1u << SCIGCR1_TXENA_BIT);
}

void sci_enable_rx(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) |= (1u << SCIGCR1_RXENA_BIT);
}

void sci_disable_rx(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) &= ~(1u << SCIGCR1_RXENA_BIT);
}

int sci_write_byte(uint8_t data)
{
    /* Wait for TXRDY */
    if (sci_wait_flag(SCIFLR_TXRDY_BIT, SCI_TIMEOUT) != 0) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCITD */
    REG32(SCITD) = (uint32_t)data;

    /* Wait for TX_EMPTY to confirm transmission */
    if (sci_wait_flag(SCIFLR_TX_EMPTY_BIT, SCI_TIMEOUT) != 0) {
        return -1;
    }

    return 0;
}

int sci_read_byte(uint8_t *data)
{
    uint32_t val;

    if (data == (void *)0) {
        return -1;
    }

    /* Wait for RXRDY */
    if (sci_wait_flag(SCIFLR_RXRDY_BIT, SCI_TIMEOUT) != 0) {
        return -1;
    }

    /* [prov] regs.yaml:SCI.SCIRD */
    val = REG32(SCIRD);
    *data = (uint8_t)(val & 0xFFu);

    return 0;
}

int sci_write(const uint8_t *buf, uint32_t len)
{
    uint32_t i;
    int ret;

    if (buf == (void *)0) {
        return -1;
    }

    for (i = 0; i < len; i++) {
        ret = sci_write_byte(buf[i]);
        if (ret != 0) {
            return (int)i;
        }
    }

    return (int)len;
}

int sci_read(uint8_t *buf, uint32_t len)
{
    uint32_t i;
    int ret;

    if (buf == (void *)0) {
        return -1;
    }

    for (i = 0; i < len; i++) {
        ret = sci_read_byte(&buf[i]);
        if (ret != 0) {
            return (int)i;
        }
    }

    return (int)len;
}

int sci_tx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCIFLR) & (1u << SCIFLR_TXRDY_BIT)) ? 1 : 0;
}

int sci_rx_ready(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCIFLR) & (1u << SCIFLR_RXRDY_BIT)) ? 1 : 0;
}

int sci_tx_empty(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCIFLR) & (1u << SCIFLR_TX_EMPTY_BIT)) ? 1 : 0;
}

int sci_is_busy(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return (REG32(SCIFLR) & (1u << SCIFLR_BUSY_BIT)) ? 1 : 0;
}

uint32_t sci_get_flags(void)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    return REG32(SCIFLR);
}

void sci_clear_flags(uint32_t flags)
{
    /* [prov] regs.yaml:SCI.SCIFLR */
    /* Write 1 to clear (RWC fields) */
    REG32(SCIFLR) = flags;
}

void sci_enable_loopback(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) |= (1u << SCIGCR1_LOOP_BACK_BIT);
}

void sci_disable_loopback(void)
{
    /* [prov] regs.yaml:SCI.SCIGCR1 */
    REG32(SCIGCR1) &= ~(1u << SCIGCR1_LOOP_BACK_BIT);
}

void sci_enable_iodft_loopback(void)
{
    /* [prov] regs.yaml:SCI.IODFTCTRL */
    REG32(IODFTCTRL) |= (1u << IODFTCTRL_LPB_ENA_BIT);
}

void sci_disable_iodft_loopback(void)
{
    /* [prov] regs.yaml:SCI.IODFTCTRL */
    REG32(IODFTCTRL) &= ~(1u << IODFTCTRL_LPB_ENA_BIT);
}

int sci_loopback_test(void)
{
    uint8_t test_pattern[4];
    uint8_t received[4];
    uint32_t i;
    int ret;
    uint32_t loopback_was_enabled;

    test_pattern[0] = 0x55u;
    test_pattern[1] = 0xAAu;
    test_pattern[2] = 0x0Fu;
    test_pattern[3] = 0xF0u;

    /* [prov] regs.yaml:SCI.SCIGCR1 */
    loopback_was_enabled = (REG32(SCIGCR1) & (1u << SCIGCR1_LOOP_BACK_BIT)) ? 1u : 0u;

    if (loopback_was_enabled == 0u) {
        sci_enable_loopback();
    }

    /* Transmit test pattern */
    ret = sci_write(test_pattern, 4u);
    if (ret != 4) {
        if (loopback_was_enabled == 0u) {
            sci_disable_loopback();
        }
        return -1;
    }

    /* Receive data back */
    ret = sci_read(received, 4u);
    if (ret != 4) {
        if (loopback_was_enabled == 0u) {
            sci_disable_loopback();
        }
        return -1;
    }

    /* Verify */
    for (i = 0; i < 4u; i++) {
        if (received[i] != test_pattern[i]) {
            if (loopback_was_enabled == 0u) {
                sci_disable_loopback();
            }
            return -1;
        }
    }

    if (loopback_was_enabled == 0u) {
        sci_disable_loopback();
    }

    return 0;
}

void sci_enable_interrupt(uint32_t int_flag)
{
    /* [prov] regs.yaml:SCI.SCISETINT */
    REG32(SCISETINT) = (1u << int_flag);
}

void sci_disable_interrupt(uint32_t int_flag)
{
    /* [prov] regs.yaml:SCI.SCICLEARINT */
    REG32(SCICLEARINT) = (1u << int_flag);
}

void sci_set_interrupt_level(uint32_t int_flag, uint32_t level)
{
    if (level != 0u) {
        /* [prov] regs.yaml:SCI.SCISETINTLVL */
        REG32(SCISETINTLVL) = (1u << int_flag);
    } else {
        /* [prov] regs.yaml:SCI.SCICLEARINTLVL */
        REG32(SCICLEARINTLVL) = (1u << int_flag);
    }
}

int sci_register_isr_lvl0(sci_isr_t isr)
{
    return vim_register_isr(IRQ_SCI_LVL0_ID, isr);
}

int sci_register_isr_lvl1(sci_isr_t isr)
{
    return vim_register_isr(IRQ_SCI_LVL1_ID, isr);
}

int sci_enable_irq_lvl0(void)
{
    return vim_enable_channel(IRQ_SCI_LVL0_ID);
}

int sci_enable_irq_lvl1(void)
{
    return vim_enable_channel(IRQ_SCI_LVL1_ID);
}

int sci_disable_irq_lvl0(void)
{
    return vim_disable_channel(IRQ_SCI_LVL0_ID);
}

int sci_disable_irq_lvl1(void)
{
    return vim_disable_channel(IRQ_SCI_LVL1_ID);
}
