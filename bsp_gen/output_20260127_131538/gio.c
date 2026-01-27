/**
 * @file gio.c
 * @brief GIO driver implementation for RM46
 */

#include <stdint.h>
#include "gio.h"
#include "clock.h"

/* External VIM API */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Base address and register offsets from FACTS MIRROR */
#define GIO_BASE                 (0xFFF7BC00u)

#define GIOGCR0_OFFSET           (0x00u)
#define GIOINTDET_OFFSET         (0x08u)
#define GIOPOL_OFFSET            (0x0Cu)
#define GIOENASET_OFFSET         (0x10u)
#define GIOENACLR_OFFSET         (0x14u)
#define GIOLVLSET_OFFSET         (0x18u)
#define GIOLVLCLR_OFFSET         (0x1Cu)
#define GIOFLG_OFFSET            (0x20u)
#define GIOOFF1_OFFSET           (0x24u)
#define GIOOFF2_OFFSET           (0x28u)
#define GIOEMU1_OFFSET           (0x2Cu)
#define GIOEMU2_OFFSET           (0x30u)
#define GIODIRA_OFFSET           (0x34u)
#define GIODINA_OFFSET           (0x38u)
#define GIODOUTA_OFFSET          (0x3Cu)
#define GIODSETA_OFFSET          (0x40u)
#define GIODCLRA_OFFSET          (0x44u)
#define GIOPDRA_OFFSET           (0x48u)
#define GIOPULDISA_OFFSET        (0x4Cu)
#define GIOPSLA_OFFSET           (0x50u)
#define GIODIRB_OFFSET           (0x54u)
#define GIODINB_OFFSET           (0x58u)
#define GIODOUTB_OFFSET          (0x5Cu)
#define GIODSETB_OFFSET          (0x60u)
#define GIODCLRB_OFFSET          (0x64u)
#define GIOPDRB_OFFSET           (0x68u)
#define GIOPULDISB_OFFSET        (0x6Cu)
#define GIOPSLB_OFFSET           (0x70u)

#define GIOGCR0_RESET_BIT        (0x00000001u)

#define GIO_A_IRQ_ID             (9u)
#define GIO_B_IRQ_ID             (23u)

/* Register accessor macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* Helper: get register address for port-specific registers */
static uint32_t gio_get_port_reg_base(gio_port_t port)
{
    if (port == GIO_PORT_A) {
        return GIO_BASE + GIODIRA_OFFSET;
    } else {
        return GIO_BASE + GIODIRB_OFFSET;
    }
}

void gio_init(void)
{
    int ret;

    /* Enable VCLK clock for GIO */
    ret = clock_enable(CLOCKREF_VCLK);
    (void)ret; /* Suppress unused warning if not checking errors */

    /* Bring GIO module out of reset */
    /* [prov] regs.yaml:GIO.GIOGCR0 */
    REG32(GIO_BASE + GIOGCR0_OFFSET) = GIOGCR0_RESET_BIT;
}

void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir)
{
    uint32_t reg_addr;
    uint32_t val;

    reg_addr = gio_get_port_reg_base(port);

    /* [prov] regs.yaml:GIO.GIODIRA / GIODIRB */
    val = REG32(reg_addr);
    if (dir == GIO_DIR_OUTPUT) {
        val |= pin_mask;
    } else {
        val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = val;
}

void gio_write_port(gio_port_t port, uint8_t value)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIODOUTA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIODOUTB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA / GIODOUTB */
    REG32(reg_addr) = value;
}

void gio_set_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIODSETA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIODSETB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODSETA / GIODSETB */
    REG32(reg_addr) = pin_mask;
}

void gio_clear_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIODCLRA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIODCLRB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODCLRA / GIODCLRB */
    REG32(reg_addr) = pin_mask;
}

uint8_t gio_read_port(gio_port_t port)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIODINA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIODINB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODINA / GIODINB */
    return (uint8_t)(REG32(reg_addr) & 0xFFu);
}

void gio_toggle_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;
    uint32_t val;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIODOUTA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIODOUTB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA / GIODOUTB */
    val = REG32(reg_addr);
    val ^= pin_mask;
    REG32(reg_addr) = val;
}

void gio_configure_pull(gio_port_t port, uint8_t pin_mask, uint32_t enable, gio_pull_t pull)
{
    uint32_t puldis_addr;
    uint32_t psl_addr;
    uint32_t val;

    if (port == GIO_PORT_A) {
        puldis_addr = GIO_BASE + GIOPULDISA_OFFSET;
        psl_addr = GIO_BASE + GIOPSLA_OFFSET;
    } else {
        puldis_addr = GIO_BASE + GIOPULDISB_OFFSET;
        psl_addr = GIO_BASE + GIOPSLB_OFFSET;
    }

    /* Configure pull disable register */
    /* [prov] regs.yaml:GIO.GIOPULDISA / GIOPULDISB */
    val = REG32(puldis_addr);
    if (enable) {
        val &= ~((uint32_t)pin_mask); /* 0 = enabled */
    } else {
        val |= pin_mask; /* 1 = disabled */
    }
    REG32(puldis_addr) = val;

    /* Configure pull select register (only matters if enabled) */
    /* [prov] regs.yaml:GIO.GIOPSLA / GIOPSLB */
    if (enable) {
        val = REG32(psl_addr);
        if (pull == GIO_PULL_UP) {
            val |= pin_mask;
        } else {
            val &= ~((uint32_t)pin_mask);
        }
        REG32(psl_addr) = val;
    }
}

void gio_set_output_mode(gio_port_t port, uint8_t pin_mask, gio_output_mode_t mode)
{
    uint32_t reg_addr;
    uint32_t val;

    if (port == GIO_PORT_A) {
        reg_addr = GIO_BASE + GIOPDRA_OFFSET;
    } else {
        reg_addr = GIO_BASE + GIOPDRB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIOPDRA / GIOPDRB */
    val = REG32(reg_addr);
    if (mode == GIO_OUTPUT_OPENDRAIN) {
        val |= pin_mask;
    } else {
        val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = val;
}

void gio_set_interrupt_detect(gio_port_t port, uint8_t pin_mask, gio_int_detect_t detect)
{
    uint32_t val;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOINTDET */
    val = REG32(GIO_BASE + GIOINTDET_OFFSET);
    if (detect == GIO_INT_BOTH_EDGES) {
        val |= ((uint32_t)pin_mask << shift);
    } else {
        val &= ~((uint32_t)pin_mask << shift);
    }
    REG32(GIO_BASE + GIOINTDET_OFFSET) = val;
}

void gio_set_interrupt_polarity(gio_port_t port, uint8_t pin_mask, gio_int_polarity_t polarity)
{
    uint32_t val;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOPOL */
    val = REG32(GIO_BASE + GIOPOL_OFFSET);
    if (polarity == GIO_INT_RISING) {
        val |= ((uint32_t)pin_mask << shift);
    } else {
        val &= ~((uint32_t)pin_mask << shift);
    }
    REG32(GIO_BASE + GIOPOL_OFFSET) = val;
}

void gio_set_interrupt_priority(gio_port_t port, uint8_t pin_mask, gio_int_priority_t priority)
{
    uint32_t set_addr;
    uint32_t clr_addr;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    set_addr = GIO_BASE + GIOLVLSET_OFFSET;
    clr_addr = GIO_BASE + GIOLVLCLR_OFFSET;

    if (priority == GIO_INT_PRIO_HIGH) {
        /* [prov] regs.yaml:GIO.GIOLVLSET */
        REG32(set_addr) = ((uint32_t)pin_mask << shift);
    } else {
        /* [prov] regs.yaml:GIO.GIOLVLCLR */
        REG32(clr_addr) = ((uint32_t)pin_mask << shift);
    }
}

void gio_enable_interrupt(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOENASET */
    REG32(GIO_BASE + GIOENASET_OFFSET) = ((uint32_t)pin_mask << shift);
}

void gio_disable_interrupt(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOENACLR */
    REG32(GIO_BASE + GIOENACLR_OFFSET) = ((uint32_t)pin_mask << shift);
}

uint8_t gio_get_interrupt_flags(gio_port_t port)
{
    uint32_t val;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOFLG */
    val = REG32(GIO_BASE + GIOFLG_OFFSET);
    return (uint8_t)((val >> shift) & 0xFFu);
}

void gio_clear_interrupt_flags(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOFLG */
    REG32(GIO_BASE + GIOFLG_OFFSET) = ((uint32_t)pin_mask << shift);
}

uint32_t gio_get_offset1(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF1 */
    return REG32(GIO_BASE + GIOOFF1_OFFSET) & 0x3Fu;
}

uint32_t gio_get_offset2(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF2 */
    return REG32(GIO_BASE + GIOOFF2_OFFSET) & 0x3Fu;
}

uint32_t gio_get_emu1(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU1 */
    return REG32(GIO_BASE + GIOEMU1_OFFSET) & 0x3Fu;
}

uint32_t gio_get_emu2(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU2 */
    return REG32(GIO_BASE + GIOEMU2_OFFSET) & 0x3Fu;
}

int gio_register_isr_a(gio_isr_t isr)
{
    return vim_register_isr(GIO_A_IRQ_ID, isr);
}

int gio_register_isr_b(gio_isr_t isr)
{
    return vim_register_isr(GIO_B_IRQ_ID, isr);
}

int gio_enable_irq_a(void)
{
    return vim_enable_channel(GIO_A_IRQ_ID);
}

int gio_enable_irq_b(void)
{
    return vim_enable_channel(GIO_B_IRQ_ID);
}

int gio_disable_irq_a(void)
{
    return vim_disable_channel(GIO_A_IRQ_ID);
}

int gio_disable_irq_b(void)
{
    return vim_disable_channel(GIO_B_IRQ_ID);
}

int gio_self_test_loopback(gio_port_t port, uint8_t pin_mask, uint8_t test_pattern)
{
    uint8_t readback;

    /* Configure pins as outputs */
    gio_set_direction(port, pin_mask, GIO_DIR_OUTPUT);

    /* Write test pattern */
    gio_write_port(port, test_pattern);

    /* Read back from DOUT register (not DIN, to verify output latch) */
    if (port == GIO_PORT_A) {
        /* [prov] regs.yaml:GIO.GIODOUTA */
        readback = (uint8_t)(REG32(GIO_BASE + GIODOUTA_OFFSET) & 0xFFu);
    } else {
        /* [prov] regs.yaml:GIO.GIODOUTB */
        readback = (uint8_t)(REG32(GIO_BASE + GIODOUTB_OFFSET) & 0xFFu);
    }

    /* Verify only the specified pins */
    if ((readback & pin_mask) == (test_pattern & pin_mask)) {
        return 0; /* Success */
    } else {
        return -1; /* Mismatch */
    }
}