/**
 * @file gio.c
 * @brief GIO driver implementation
 */

#include <stdint.h>
#include "gio.h"
#include "clock.h"

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* Base address and register offsets from FACTS MIRROR */
#define GIO_BASE                (0xFFF7BC00u)
#define GIOGCRO_OFFSET          (0x00u)
#define GIOINTDET_OFFSET        (0x08u)
#define GIOPOL_OFFSET           (0x0Cu)
#define GIOENASET_OFFSET        (0x10u)
#define GIOENACLR_OFFSET        (0x14u)
#define GIOLVLSET_OFFSET        (0x18u)
#define GIOLVLCLR_OFFSET        (0x1Cu)
#define GIOFLG_OFFSET           (0x20u)
#define GIOOFF1_OFFSET          (0x24u)
#define GIOOFF2_OFFSET          (0x28u)
#define GIOEMU1_OFFSET          (0x2Cu)
#define GIOEMU2_OFFSET          (0x30u)
#define GIODIRA_OFFSET          (0x34u)
#define GIODINA_OFFSET          (0x38u)
#define GIODOUTA_OFFSET         (0x3Cu)
#define GIODSETA_OFFSET         (0x40u)
#define GIODCLRA_OFFSET         (0x44u)
#define GIOPDRA_OFFSET          (0x48u)
#define GIOPULDISA_OFFSET       (0x4Cu)
#define GIOPSLA_OFFSET          (0x50u)
#define GIODIRB_OFFSET          (0x54u)
#define GIODINB_OFFSET          (0x58u)
#define GIODOUTB_OFFSET         (0x5Cu)
#define GIODSETB_OFFSET         (0x60u)
#define GIODCLRB_OFFSET         (0x64u)
#define GIOPDRB_OFFSET          (0x68u)
#define GIOPULDISB_OFFSET       (0x6Cu)
#define GIOPSLB_OFFSET          (0x70u)

#define GIOGCRO_RESET_BIT       (0x00000001u)

/* VIM API prototypes */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Port register offset tables */
static const uint32_t dir_offsets[2]     = { GIODIRA_OFFSET,    GIODIRB_OFFSET };
static const uint32_t din_offsets[2]     = { GIODINA_OFFSET,    GIODINB_OFFSET };
static const uint32_t dout_offsets[2]    = { GIODOUTA_OFFSET,   GIODOUTB_OFFSET };
static const uint32_t dset_offsets[2]    = { GIODSETA_OFFSET,   GIODSETB_OFFSET };
static const uint32_t dclr_offsets[2]    = { GIODCLRA_OFFSET,   GIODCLRB_OFFSET };
static const uint32_t pdr_offsets[2]     = { GIOPDRA_OFFSET,    GIOPDRB_OFFSET };
static const uint32_t puldis_offsets[2]  = { GIOPULDISA_OFFSET, GIOPULDISB_OFFSET };
static const uint32_t psl_offsets[2]     = { GIOPSLA_OFFSET,    GIOPSLB_OFFSET };

void gio_init(void)
{
    /* Enable VCLK clock */
    clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:GIO.GIOGCRO */
    /* Bring GIO out of reset by setting RESET bit */
    REG32(GIO_BASE + GIOGCRO_OFFSET) = GIOGCRO_RESET_BIT;
}

void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    reg_addr = GIO_BASE + dir_offsets[port];

    /* [prov] regs.yaml:GIO.GIODIRA / GIO.GIODIRB */
    reg_val = REG32(reg_addr);
    if (dir == GIO_DIR_OUTPUT) {
        reg_val |= pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

uint8_t gio_read_port(gio_port_t port)
{
    uint32_t reg_addr;

    reg_addr = GIO_BASE + din_offsets[port];

    /* [prov] regs.yaml:GIO.GIODINA / GIO.GIODINB */
    return (uint8_t)(REG32(reg_addr) & 0xFFu);
}

void gio_write_port(gio_port_t port, uint8_t value)
{
    uint32_t reg_addr;

    reg_addr = GIO_BASE + dout_offsets[port];

    /* [prov] regs.yaml:GIO.GIODOUTA / GIO.GIODOUTB */
    REG32(reg_addr) = (uint32_t)value;
}

void gio_set_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    reg_addr = GIO_BASE + dset_offsets[port];

    /* [prov] regs.yaml:GIO.GIODSETA / GIO.GIODSETB */
    REG32(reg_addr) = (uint32_t)pin_mask;
}

void gio_clear_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;

    reg_addr = GIO_BASE + dclr_offsets[port];

    /* [prov] regs.yaml:GIO.GIODCLRA / GIO.GIODCLRB */
    REG32(reg_addr) = (uint32_t)pin_mask;
}

void gio_toggle_pins(gio_port_t port, uint8_t pin_mask)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    reg_addr = GIO_BASE + dout_offsets[port];

    /* [prov] regs.yaml:GIO.GIODOUTA / GIO.GIODOUTB */
    reg_val = REG32(reg_addr);
    reg_val ^= (uint32_t)pin_mask;
    REG32(reg_addr) = reg_val;
}

void gio_set_open_drain(gio_port_t port, uint8_t pin_mask, gio_open_drain_t mode)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    reg_addr = GIO_BASE + pdr_offsets[port];

    /* [prov] regs.yaml:GIO.GIOPDRA / GIO.GIOPDRB */
    reg_val = REG32(reg_addr);
    if (mode == GIO_MODE_OPEN_DRAIN) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_pull_disable(gio_port_t port, uint8_t pin_mask, uint8_t disable)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    reg_addr = GIO_BASE + puldis_offsets[port];

    /* [prov] regs.yaml:GIO.GIOPULDISA / GIO.GIOPULDISB */
    reg_val = REG32(reg_addr);
    if (disable) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_pull_select(gio_port_t port, uint8_t pin_mask, gio_pull_sel_t sel)
{
    uint32_t reg_addr;
    uint32_t reg_val;

    reg_addr = GIO_BASE + psl_offsets[port];

    /* [prov] regs.yaml:GIO.GIOPSLA / GIO.GIOPSLB */
    reg_val = REG32(reg_addr);
    if (sel == GIO_PULL_UP) {
        reg_val |= (uint32_t)pin_mask;
    } else {
        reg_val &= ~((uint32_t)pin_mask);
    }
    REG32(reg_addr) = reg_val;
}

void gio_set_int_detect(gio_port_t port, uint8_t pin_mask, gio_int_detect_t detect)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t reg_val;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOINTDET */
    reg_val = REG32(GIO_BASE + GIOINTDET_OFFSET);
    if (detect == GIO_INT_EDGE_BOTH) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + GIOINTDET_OFFSET) = reg_val;
}

void gio_set_int_polarity(gio_port_t port, uint8_t pin_mask, gio_int_pol_t pol)
{
    uint32_t shift;
    uint32_t mask;
    uint32_t reg_val;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOPOL */
    reg_val = REG32(GIO_BASE + GIOPOL_OFFSET);
    if (pol == GIO_INT_POL_RISING) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + GIOPOL_OFFSET) = reg_val;
}

void gio_enable_int(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;
    uint32_t mask;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOENASET */
    REG32(GIO_BASE + GIOENASET_OFFSET) = mask;
}

void gio_disable_int(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;
    uint32_t mask;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOENACLR */
    REG32(GIO_BASE + GIOENACLR_OFFSET) = mask;
}

void gio_set_int_priority(gio_port_t port, uint8_t pin_mask, gio_int_prio_t prio)
{
    uint32_t shift;
    uint32_t mask;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    if (prio == GIO_INT_PRIO_HIGH) {
        /* [prov] regs.yaml:GIO.GIOLVLSET */
        REG32(GIO_BASE + GIOLVLSET_OFFSET) = mask;
    } else {
        /* [prov] regs.yaml:GIO.GIOLVLCLR */
        REG32(GIO_BASE + GIOLVLCLR_OFFSET) = mask;
    }
}

uint8_t gio_get_int_flags(gio_port_t port)
{
    uint32_t shift;
    uint32_t reg_val;

    shift = port * 8u;

    /* [prov] regs.yaml:GIO.GIOFLG */
    reg_val = REG32(GIO_BASE + GIOFLG_OFFSET);
    return (uint8_t)((reg_val >> shift) & 0xFFu);
}

void gio_clear_int_flags(gio_port_t port, uint8_t pin_mask)
{
    uint32_t shift;
    uint32_t mask;

    shift = port * 8u;
    mask = ((uint32_t)pin_mask) << shift;

    /* [prov] regs.yaml:GIO.GIOFLG */
    REG32(GIO_BASE + GIOFLG_OFFSET) = mask;
}

uint32_t gio_read_offset1(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF1 */
    return REG32(GIO_BASE + GIOOFF1_OFFSET) & 0x3Fu;
}

uint32_t gio_read_offset2(void)
{
    /* [prov] regs.yaml:GIO.GIOOFF2 */
    return REG32(GIO_BASE + GIOOFF2_OFFSET) & 0x3Fu;
}

uint32_t gio_read_emu1(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU1 */
    return REG32(GIO_BASE + GIOEMU1_OFFSET) & 0x3Fu;
}

uint32_t gio_read_emu2(void)
{
    /* [prov] regs.yaml:GIO.GIOEMU2 */
    return REG32(GIO_BASE + GIOEMU2_OFFSET) & 0x3Fu;
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