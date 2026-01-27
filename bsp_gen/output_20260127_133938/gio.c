/**
 * @file gio.c
 * @brief General-Purpose Input/Output (GIO) Module Driver Implementation
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

/* GIO base address and register offsets */
#define GIO_BASE            (0xFFF7BC00u)
#define GIOGCRO_OFFSET      (0x00u)
#define GIOINTDET_OFFSET    (0x08u)
#define GIOPOL_OFFSET       (0x0Cu)
#define GIOENASET_OFFSET    (0x10u)
#define GIOENACLR_OFFSET    (0x14u)
#define GIOLVLSET_OFFSET    (0x18u)
#define GIOLVLCLR_OFFSET    (0x1Cu)
#define GIOFLG_OFFSET       (0x20u)
#define GIOOFF1_OFFSET      (0x24u)
#define GIOOFF2_OFFSET      (0x28u)
#define GIOEMU1_OFFSET      (0x2Cu)
#define GIOEMU2_OFFSET      (0x30u)
#define GIODIRA_OFFSET      (0x34u)
#define GIODINA_OFFSET      (0x38u)
#define GIODOUTA_OFFSET     (0x3Cu)
#define GIODSETA_OFFSET     (0x40u)
#define GIODCLRA_OFFSET     (0x44u)
#define GIOPDRA_OFFSET      (0x48u)
#define GIOPULDISA_OFFSET   (0x4Cu)
#define GIOPSLA_OFFSET      (0x50u)
#define GIODIRB_OFFSET      (0x54u)
#define GIODINB_OFFSET      (0x58u)
#define GIODOUTB_OFFSET     (0x5Cu)
#define GIODSETB_OFFSET     (0x60u)
#define GIODCLRB_OFFSET     (0x64u)
#define GIOPDRB_OFFSET      (0x68u)
#define GIOPULDISB_OFFSET   (0x6Cu)
#define GIOPSLB_OFFSET      (0x70u)

/* GIO register addresses */
#define GIOGCRO             (GIO_BASE + GIOGCRO_OFFSET)
#define GIOINTDET           (GIO_BASE + GIOINTDET_OFFSET)
#define GIOPOL              (GIO_BASE + GIOPOL_OFFSET)
#define GIOENASET           (GIO_BASE + GIOENASET_OFFSET)
#define GIOENACLR           (GIO_BASE + GIOENACLR_OFFSET)
#define GIOLVLSET           (GIO_BASE + GIOLVLSET_OFFSET)
#define GIOLVLCLR           (GIO_BASE + GIOLVLCLR_OFFSET)
#define GIOFLG              (GIO_BASE + GIOFLG_OFFSET)
#define GIOOFF1             (GIO_BASE + GIOOFF1_OFFSET)
#define GIOOFF2             (GIO_BASE + GIOOFF2_OFFSET)
#define GIOEMU1             (GIO_BASE + GIOEMU1_OFFSET)
#define GIOEMU2             (GIO_BASE + GIOEMU2_OFFSET)
#define GIODIRA             (GIO_BASE + GIODIRA_OFFSET)
#define GIODINA             (GIO_BASE + GIODINA_OFFSET)
#define GIODOUTA            (GIO_BASE + GIODOUTA_OFFSET)
#define GIODSETA            (GIO_BASE + GIODSETA_OFFSET)
#define GIODCLRA            (GIO_BASE + GIODCLRA_OFFSET)
#define GIOPDRA             (GIO_BASE + GIOPDRA_OFFSET)
#define GIOPULDISA          (GIO_BASE + GIOPULDISA_OFFSET)
#define GIOPSLA             (GIO_BASE + GIOPSLA_OFFSET)
#define GIODIRB             (GIO_BASE + GIODIRB_OFFSET)
#define GIODINB             (GIO_BASE + GIODINB_OFFSET)
#define GIODOUTB            (GIO_BASE + GIODOUTB_OFFSET)
#define GIODSETB            (GIO_BASE + GIODSETB_OFFSET)
#define GIODCLRB            (GIO_BASE + GIODCLRB_OFFSET)
#define GIOPDRB             (GIO_BASE + GIOPDRB_OFFSET)
#define GIOPULDISB          (GIO_BASE + GIOPULDISB_OFFSET)
#define GIOPSLB             (GIO_BASE + GIOPSLB_OFFSET)

/* GIO constants */
#define GIO_RESET_ENABLE    (0x00000001u)

void gio_init(void)
{
    /* Enable VCLK clock for GIO */
    clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:GIO.GIOGCRO */
    /* Bring GIO out of reset by setting bit 0 */
    REG32(GIOGCRO) = GIO_RESET_ENABLE;
}

void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_addr = GIODIRA;
    } else {
        reg_addr = GIODIRB;
    }

    /* [prov] regs.yaml:GIO.GIODIRA / GIO.GIODIRB */
    reg_val = REG32(reg_addr);
    if (dir == GIO_DIR_OUTPUT) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

uint8_t gio_read_port(gio_port_t port)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODINA;
    } else {
        reg_addr = GIODINB;
    }

    /* [prov] regs.yaml:GIO.GIODINA / GIO.GIODINB */
    return (uint8_t)(REG32(reg_addr) & 0xFFu);
}

void gio_write_port(gio_port_t port, uint8_t value)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODOUTA;
    } else {
        reg_addr = GIODOUTB;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA / GIO.GIODOUTB */
    REG32(reg_addr) = (uint32_t)value;
}

void gio_set_bits(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODSETA;
    } else {
        reg_addr = GIODSETB;
    }

    /* [prov] regs.yaml:GIO.GIODSETA / GIO.GIODSETB */
    REG32(reg_addr) = (uint32_t)pin_mask;
}

void gio_clear_bits(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    if (port == GIO_PORT_A) {
        reg_addr = GIODCLRA;
    } else {
        reg_addr = GIODCLRB;
    }

    /* [prov] regs.yaml:GIO.GIODCLRA / GIO.GIODCLRB */
    REG32(reg_addr) = (uint32_t)pin_mask;
}

void gio_toggle_bits(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;
    uint8_t current;

    if (port == GIO_PORT_A) {
        reg_addr = GIODOUTA;
    } else {
        reg_addr = GIODOUTB;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA / GIO.GIODOUTB */
    current = (uint8_t)(REG32(reg_addr) & 0xFFu);
    REG32(reg_addr) = (uint32_t)(current ^ pin_mask);
}

void gio_set_open_drain(gio_port_t port, uint8_t pin_mask, gio_od_t mode)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_addr = GIOPDRA;
    } else {
        reg_addr = GIOPDRB;
    }

    /* [prov] regs.yaml:GIO.GIOPDRA / GIO.GIOPDRB */
    reg_val = REG32(reg_addr);
    if (mode == GIO_OPEN_DRAIN) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_pull_enable(gio_port_t port, uint8_t pin_mask, uint8_t enable)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_addr = GIOPULDISA;
    } else {
        reg_addr = GIOPULDISB;
    }

    /* [prov] regs.yaml:GIO.GIOPULDISA / GIO.GIOPULDISB */
    reg_val = REG32(reg_addr);
    if (enable) {
        /* Enable pull = disable pull disable bit */
        reg_val &= ~((uint32_t)pin_mask);
    } else {
        /* Disable pull = set pull disable bit */
        reg_val |= (uint32_t)pin_mask;
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_pull_select(gio_port_t port, uint8_t pin_mask, gio_pull_t pull)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_addr = GIOPSLA;
    } else {
        reg_addr = GIOPSLB;
    }

    /* [prov] regs.yaml:GIO.GIOPSLA / GIO.GIOPSLB */
    reg_val = REG32(reg_addr);
    if (pull == GIO_PULL_UP) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_int_detect(gio_port_t port, uint8_t pin_mask, gio_int_det_t det)
{
    uint32_t reg_val;
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOINTDET */
    reg_val = REG32(GIOINTDET);
    if (det == GIO_INT_BOTH_EDGES) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIOINTDET) = reg_val;
}

void gio_set_int_polarity(gio_port_t port, uint8_t pin_mask, gio_int_pol_t pol)
{
    uint32_t reg_val;
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOPOL */
    reg_val = REG32(GIOPOL);
    if (pol == GIO_POL_RISING) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIOPOL) = reg_val;
}

void gio_enable_int(gio_port_t port, uint8_t pin_mask)
{
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOENASET */
    REG32(GIOENASET) = mask;
}

void gio_disable_int(gio_port_t port, uint8_t pin_mask)
{
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOENACLR */
    REG32(GIOENACLR) = mask;
}

void gio_set_int_priority(gio_port_t port, uint8_t pin_mask, gio_int_prio_t prio)
{
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    if (prio == GIO_PRIO_HIGH) {
        /* [prov] regs.yaml:GIO.GIOLVLSET */
        REG32(GIOLVLSET) = mask;
    } else {
        /* [prov] regs.yaml:GIO.GIOLVLCLR */
        REG32(GIOLVLCLR) = mask;
    }
}

uint8_t gio_read_int_flags(gio_port_t port)
{
    uint32_t reg_val;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;

    /* [prov] regs.yaml:GIO.GIOFLG */
    reg_val = REG32(GIOFLG);
    return (uint8_t)((reg_val >> shift) & 0xFFu);
}

void gio_clear_int_flags(gio_port_t port, uint8_t pin_mask)
{
    uint32_t mask;
    uint32_t shift;

    shift = (port == GIO_PORT_A) ? 0u : 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOFLG */
    REG32(GIOFLG) = mask;
}

uint8_t gio_read_offset1(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF1 */
    return (uint8_t)(REG32(GIOOFF1) & 0x3Fu);
}

uint8_t gio_read_offset2(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF2 */
    return (uint8_t)(REG32(GIOOFF2) & 0x3Fu);
}

uint8_t gio_read_emu1(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU1 */
    return (uint8_t)(REG32(GIOEMU1) & 0x3Fu);
}

uint8_t gio_read_emu2(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU2 */
    return (uint8_t)(REG32(GIOEMU2) & 0x3Fu);
}

int gio_register_isr(uint32_t channel_id, gio_isr_t isr)
{
    return vim_register_isr(channel_id, isr);
}

int gio_enable_vim_channel(uint32_t channel_id)
{
    return vim_enable_channel(channel_id);
}

int gio_disable_vim_channel(uint32_t channel_id)
{
    return vim_disable_channel(channel_id);
}