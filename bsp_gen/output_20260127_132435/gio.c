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

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* Base address */
#define GIO_BASE 0xFFF7BC00u

/* Register offsets */
#define GIOGCRO_OFFSET    0x00u
#define GIOINTDET_OFFSET  0x08u
#define GIOPOL_OFFSET     0x0Cu
#define GIOENASET_OFFSET  0x10u
#define GIOENACLR_OFFSET  0x14u
#define GIOLVLSET_OFFSET  0x18u
#define GIOLVLCLR_OFFSET  0x1Cu
#define GIOFLG_OFFSET     0x20u
#define GIOOFF1_OFFSET    0x24u
#define GIOOFF2_OFFSET    0x28u
#define GIOEMU1_OFFSET    0x2Cu
#define GIOEMU2_OFFSET    0x30u
#define GIODIRA_OFFSET    0x34u
#define GIODINA_OFFSET    0x38u
#define GIODOUTA_OFFSET   0x3Cu
#define GIODSETA_OFFSET   0x40u
#define GIODCLRA_OFFSET   0x44u
#define GIOPDRA_OFFSET    0x48u
#define GIOPULDISA_OFFSET 0x4Cu
#define GIOPSLA_OFFSET    0x50u
#define GIODIRB_OFFSET    0x54u
#define GIODINB_OFFSET    0x58u
#define GIODOUTB_OFFSET   0x5Cu
#define GIODSETB_OFFSET   0x60u
#define GIODCLRB_OFFSET   0x64u
#define GIOPDRB_OFFSET    0x68u
#define GIOPULDISB_OFFSET 0x6Cu
#define GIOPSLB_OFFSET    0x70u

/* Register addresses */
#define GIOGCRO    (GIO_BASE + GIOGCRO_OFFSET)
#define GIOINTDET  (GIO_BASE + GIOINTDET_OFFSET)
#define GIOPOL     (GIO_BASE + GIOPOL_OFFSET)
#define GIOENASET  (GIO_BASE + GIOENASET_OFFSET)
#define GIOENACLR  (GIO_BASE + GIOENACLR_OFFSET)
#define GIOLVLSET  (GIO_BASE + GIOLVLSET_OFFSET)
#define GIOLVLCLR  (GIO_BASE + GIOLVLCLR_OFFSET)
#define GIOFLG     (GIO_BASE + GIOFLG_OFFSET)
#define GIOOFF1    (GIO_BASE + GIOOFF1_OFFSET)
#define GIOOFF2    (GIO_BASE + GIOOFF2_OFFSET)
#define GIOEMU1    (GIO_BASE + GIOEMU1_OFFSET)
#define GIOEMU2    (GIO_BASE + GIOEMU2_OFFSET)
#define GIODIRA    (GIO_BASE + GIODIRA_OFFSET)
#define GIODINA    (GIO_BASE + GIODINA_OFFSET)
#define GIODOUTA   (GIO_BASE + GIODOUTA_OFFSET)
#define GIODSETA   (GIO_BASE + GIODSETA_OFFSET)
#define GIODCLRA   (GIO_BASE + GIODCLRA_OFFSET)
#define GIOPDRA    (GIO_BASE + GIOPDRA_OFFSET)
#define GIOPULDISA (GIO_BASE + GIOPULDISA_OFFSET)
#define GIOPSLA    (GIO_BASE + GIOPSLA_OFFSET)
#define GIODIRB    (GIO_BASE + GIODIRB_OFFSET)
#define GIODINB    (GIO_BASE + GIODINB_OFFSET)
#define GIODOUTB   (GIO_BASE + GIODOUTB_OFFSET)
#define GIODSETB   (GIO_BASE + GIODSETB_OFFSET)
#define GIODCLRB   (GIO_BASE + GIODCLRB_OFFSET)
#define GIOPDRB    (GIO_BASE + GIOPDRB_OFFSET)
#define GIOPULDISB (GIO_BASE + GIOPULDISB_OFFSET)
#define GIOPSLB    (GIO_BASE + GIOPSLB_OFFSET)

/* Constants */
#define GCR0_INIT_VALUE 0x00000001u

void gio_init(void)
{
    /* Enable VCLK clock */
    clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:GIO.GIOGCRO */
    REG32(GIOGCRO) = GCR0_INIT_VALUE;
}

void gio_set_direction(gio_port_t port, uint8_t pin, gio_dir_t dir)
{
    uint32_t reg_addr;
    uint32_t mask;
    uint32_t val;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIODIRA;
    } else {
        reg_addr = GIODIRB;
    }

    /* [prov] regs.yaml:GIO.GIODIRA or GIO.GIODIRB */
    val = REG32(reg_addr);
    if (dir == GIO_DIR_OUTPUT) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(reg_addr) = val;
}

void gio_set_direction_mask(gio_port_t port, uint8_t mask)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODIRA;
    } else {
        reg_addr = GIODIRB;
    }

    /* [prov] regs.yaml:GIO.GIODIRA or GIO.GIODIRB */
    REG32(reg_addr) = mask;
}

void gio_set_pin(gio_port_t port, uint8_t pin)
{
    uint32_t reg_addr;
    uint32_t mask;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIODSETA;
    } else {
        reg_addr = GIODSETB;
    }

    /* [prov] regs.yaml:GIO.GIODSETA or GIO.GIODSETB */
    REG32(reg_addr) = mask;
}

void gio_clear_pin(gio_port_t port, uint8_t pin)
{
    uint32_t reg_addr;
    uint32_t mask;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIODCLRA;
    } else {
        reg_addr = GIODCLRB;
    }

    /* [prov] regs.yaml:GIO.GIODCLRA or GIO.GIODCLRB */
    REG32(reg_addr) = mask;
}

void gio_toggle_pin(gio_port_t port, uint8_t pin)
{
    uint32_t dout_addr;
    uint32_t dset_addr;
    uint32_t dclr_addr;
    uint32_t mask;
    uint32_t current;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        dout_addr = GIODOUTA;
        dset_addr = GIODSETA;
        dclr_addr = GIODCLRA;
    } else {
        dout_addr = GIODOUTB;
        dset_addr = GIODSETB;
        dclr_addr = GIODCLRB;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA or GIO.GIODOUTB */
    current = REG32(dout_addr);

    if (current & mask) {
        /* [prov] regs.yaml:GIO.GIODCLRA or GIO.GIODCLRB */
        REG32(dclr_addr) = mask;
    } else {
        /* [prov] regs.yaml:GIO.GIODSETA or GIO.GIODSETB */
        REG32(dset_addr) = mask;
    }
}

void gio_write_port(gio_port_t port, uint8_t value)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODOUTA;
    } else {
        reg_addr = GIODOUTB;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA or GIO.GIODOUTB */
    REG32(reg_addr) = value;
}

uint8_t gio_read_pin(gio_port_t port, uint8_t pin)
{
    uint32_t reg_addr;
    uint32_t val;

    if (port == GIO_PORT_A) {
        reg_addr = GIODINA;
    } else {
        reg_addr = GIODINB;
    }

    /* [prov] regs.yaml:GIO.GIODINA or GIO.GIODINB */
    val = REG32(reg_addr);

    return (val & (1u << pin)) ? 1u : 0u;
}

uint8_t gio_read_port(gio_port_t port)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODINA;
    } else {
        reg_addr = GIODINB;
    }

    /* [prov] regs.yaml:GIO.GIODINA or GIO.GIODINB */
    return (uint8_t)REG32(reg_addr);
}

void gio_set_output_mode(gio_port_t port, uint8_t pin, gio_output_mode_t mode)
{
    uint32_t reg_addr;
    uint32_t mask;
    uint32_t val;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIOPDRA;
    } else {
        reg_addr = GIOPDRB;
    }

    /* [prov] regs.yaml:GIO.GIOPDRA or GIO.GIOPDRB */
    val = REG32(reg_addr);
    if (mode == GIO_OPEN_DRAIN) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(reg_addr) = val;
}

void gio_set_pull_enable(gio_port_t port, uint8_t pin, gio_pull_enable_t enable)
{
    uint32_t reg_addr;
    uint32_t mask;
    uint32_t val;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIOPULDISA;
    } else {
        reg_addr = GIOPULDISB;
    }

    /* [prov] regs.yaml:GIO.GIOPULDISA or GIO.GIOPULDISB */
    val = REG32(reg_addr);
    if (enable == GIO_PULL_DISABLED) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(reg_addr) = val;
}

void gio_set_pull_select(gio_port_t port, uint8_t pin, gio_pull_select_t select)
{
    uint32_t reg_addr;
    uint32_t mask;
    uint32_t val;

    mask = (1u << pin);

    if (port == GIO_PORT_A) {
        reg_addr = GIOPSLA;
    } else {
        reg_addr = GIOPSLB;
    }

    /* [prov] regs.yaml:GIO.GIOPSLA or GIO.GIOPSLB */
    val = REG32(reg_addr);
    if (select == GIO_PULL_UP) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(reg_addr) = val;
}

void gio_set_int_detect(gio_port_t port, uint8_t pin, gio_int_detect_t detect)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t val;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOINTDET */
    val = REG32(GIOINTDET);
    if (detect == GIO_INT_BOTH_EDGES) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(GIOINTDET) = val;
}

void gio_set_int_polarity(gio_port_t port, uint8_t pin, gio_int_polarity_t polarity)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t val;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOPOL */
    val = REG32(GIOPOL);
    if (polarity == GIO_INT_POL_RISING_OR_HIGH) {
        val |= mask;
    } else {
        val &= ~mask;
    }
    REG32(GIOPOL) = val;
}

void gio_enable_int(gio_port_t port, uint8_t pin)
{
    uint32_t shift;
    uint32_t mask;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOENASET */
    REG32(GIOENASET) = mask;
}

void gio_disable_int(gio_port_t port, uint8_t pin)
{
    uint32_t shift;
    uint32_t mask;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOENACLR */
    REG32(GIOENACLR) = mask;
}

void gio_set_int_priority(gio_port_t port, uint8_t pin, gio_int_priority_t priority)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t set_addr;
    uint32_t clr_addr;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    set_addr = GIOLVLSET;
    clr_addr = GIOLVLCLR;

    if (priority == GIO_INT_PRIORITY_HIGH) {
        /* [prov] regs.yaml:GIO.GIOLVLSET */
        REG32(set_addr) = mask;
    } else {
        /* [prov] regs.yaml:GIO.GIOLVLCLR */
        REG32(clr_addr) = mask;
    }
}

void gio_clear_int_flag(gio_port_t port, uint8_t pin)
{
    uint32_t shift;
    uint32_t mask;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOFLG */
    REG32(GIOFLG) = mask;
}

uint8_t gio_get_int_flag(gio_port_t port, uint8_t pin)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t val;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = (1u << (pin + shift));

    /* [prov] regs.yaml:GIO.GIOFLG */
    val = REG32(GIOFLG);

    return (val & mask) ? 1u : 0u;
}

uint8_t gio_get_offset_high(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF1 */
    return (uint8_t)(REG32(GIOOFF1) & 0x3Fu);
}

uint8_t gio_get_offset_low(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF2 */
    return (uint8_t)(REG32(GIOOFF2) & 0x3Fu);
}

uint8_t gio_get_emu_offset_high(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU1 */
    return (uint8_t)(REG32(GIOEMU1) & 0x3Fu);
}

uint8_t gio_get_emu_offset_low(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU2 */
    return (uint8_t)(REG32(GIOEMU2) & 0x3Fu);
}

int gio_register_isr(uint32_t channel_id, gio_isr_t isr)
{
    return vim_register_isr(channel_id, isr);
}

int gio_enable_irq(uint32_t channel_id)
{
    return vim_enable_channel(channel_id);
}

int gio_disable_irq(uint32_t channel_id)
{
    return vim_disable_channel(channel_id);
}