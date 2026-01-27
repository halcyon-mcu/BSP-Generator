/**
 * @file gio.c
 * @brief GIO (General-Purpose Input/Output) Driver Implementation for TI RM46
 */

#include <stdint.h>
#include "gio.h"
#include "clock.h"

/* External VIM API (provided by system-level VIM driver) */
extern int vim_register_isr(uint32_t channel_id, void (*isr)(void));
extern int vim_enable_channel(uint32_t channel_id);
extern int vim_disable_channel(uint32_t channel_id);

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* GIO base and register offsets */
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

/* Interrupt IDs from irq.yaml */
#define GIO_IRQ_A_ID        (9u)
#define GIO_IRQ_B_ID        (23u)

/* Init value from x-ext */
#define GIO_INIT_GCR0_VALUE (0x00000001u)

void gio_init(void) {
    /* Enable VCLK clock for GIO */
    clock_enable(CLOCKREF_VCLK);

    /* [prov] regs.yaml:GIO.GIOGCRO */
    /* Bring GIO out of reset */
    REG32(GIO_BASE + GIOGCRO_OFFSET) = GIO_INIT_GCR0_VALUE;
}

void gio_set_direction(gio_port_t port, uint8_t mask, gio_dir_t dir) {
    uint32_t reg_offset;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_offset = GIODIRA_OFFSET;
    } else {
        reg_offset = GIODIRB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODIRA or GIO.GIODIRB */
    reg_val = REG32(GIO_BASE + reg_offset);
    if (dir == GIO_DIR_OUTPUT) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + reg_offset) = reg_val;
}

void gio_write_port(gio_port_t port, uint8_t value) {
    uint32_t reg_offset;

    if (port == GIO_PORT_A) {
        reg_offset = GIODOUTA_OFFSET;
    } else {
        reg_offset = GIODOUTB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODOUTA or GIO.GIODOUTB */
    REG32(GIO_BASE + reg_offset) = value;
}

uint8_t gio_read_port(gio_port_t port) {
    uint32_t reg_offset;

    if (port == GIO_PORT_A) {
        reg_offset = GIODINA_OFFSET;
    } else {
        reg_offset = GIODINB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODINA or GIO.GIODINB */
    return (uint8_t)(REG32(GIO_BASE + reg_offset) & 0xFFu);
}

void gio_set_pins(gio_port_t port, uint8_t mask) {
    uint32_t reg_offset;

    if (port == GIO_PORT_A) {
        reg_offset = GIODSETA_OFFSET;
    } else {
        reg_offset = GIODSETB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODSETA or GIO.GIODSETB */
    REG32(GIO_BASE + reg_offset) = mask;
}

void gio_clear_pins(gio_port_t port, uint8_t mask) {
    uint32_t reg_offset;

    if (port == GIO_PORT_A) {
        reg_offset = GIODCLRA_OFFSET;
    } else {
        reg_offset = GIODCLRB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIODCLRA or GIO.GIODCLRB */
    REG32(GIO_BASE + reg_offset) = mask;
}

void gio_set_opendrain(gio_port_t port, uint8_t mask, gio_opendrain_t mode) {
    uint32_t reg_offset;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_offset = GIOPDRA_OFFSET;
    } else {
        reg_offset = GIOPDRB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIOPDRA or GIO.GIOPDRB */
    reg_val = REG32(GIO_BASE + reg_offset);
    if (mode == GIO_OPEN_DRAIN) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + reg_offset) = reg_val;
}

void gio_set_pull_disable(gio_port_t port, uint8_t mask, gio_pull_dis_t pull_dis) {
    uint32_t reg_offset;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_offset = GIOPULDISA_OFFSET;
    } else {
        reg_offset = GIOPULDISB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIOPULDISA or GIO.GIOPULDISB */
    reg_val = REG32(GIO_BASE + reg_offset);
    if (pull_dis == GIO_PULL_DISABLED) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + reg_offset) = reg_val;
}

void gio_set_pull_select(gio_port_t port, uint8_t mask, gio_pull_sel_t pull_sel) {
    uint32_t reg_offset;
    uint32_t reg_val;

    if (port == GIO_PORT_A) {
        reg_offset = GIOPSLA_OFFSET;
    } else {
        reg_offset = GIOPSLB_OFFSET;
    }

    /* [prov] regs.yaml:GIO.GIOPSLA or GIO.GIOPSLB */
    reg_val = REG32(GIO_BASE + reg_offset);
    if (pull_sel == GIO_PULL_UP) {
        reg_val |= mask;
    } else {
        reg_val &= ~mask;
    }
    REG32(GIO_BASE + reg_offset) = reg_val;
}

void gio_set_int_detect(gio_port_t port, uint8_t pin, gio_int_det_t det) {
    uint32_t shift;
    uint32_t reg_val;

    shift = (uint32_t)port * 8u + pin;

    /* [prov] regs.yaml:GIO.GIOINTDET */
    reg_val = REG32(GIO_BASE + GIOINTDET_OFFSET);
    if (det == GIO_INT_BOTH_EDGES) {
        reg_val |= (1u << shift);
    } else {
        reg_val &= ~(1u << shift);
    }
    REG32(GIO_BASE + GIOINTDET_OFFSET) = reg_val;
}

void gio_set_int_polarity(gio_port_t port, uint8_t pin, gio_pol_t pol) {
    uint32_t shift;
    uint32_t reg_val;

    shift = (uint32_t)port * 8u + pin;

    /* [prov] regs.yaml:GIO.GIOPOL */
    reg_val = REG32(GIO_BASE + GIOPOL_OFFSET);
    if (pol == GIO_POL_RISING) {
        reg_val |= (1u << shift);
    } else {
        reg_val &= ~(1u << shift);
    }
    REG32(GIO_BASE + GIOPOL_OFFSET) = reg_val;
}

void gio_enable_int(gio_port_t port, uint8_t pin) {
    uint32_t shift;

    shift = (uint32_t)port * 8u + pin;

    /* [prov] regs.yaml:GIO.GIOENASET */
    REG32(GIO_BASE + GIOENASET_OFFSET) = (1u << shift);
}

void gio_disable_int(gio_port_t port, uint8_t pin) {
    uint32_t shift;

    shift = (uint32_t)port * 8u + pin;

    /* [prov] regs.yaml:GIO.GIOENACLR */
    REG32(GIO_BASE + GIOENACLR_OFFSET) = (1u << shift);
}

void gio_set_int_level(gio_port_t port, uint8_t pin, gio_int_lvl_t lvl) {
    uint32_t shift;

    shift = (uint32_t)port * 8u + pin;

    if (lvl == GIO_INT_HIGH) {
        /* [prov] regs.yaml:GIO.GIOLVLSET */
        REG32(GIO_BASE + GIOLVLSET_OFFSET) = (1u << shift);
    } else {
        /* [prov] regs.yaml:GIO.GIOLVLCLR */
        REG32(GIO_BASE + GIOLVLCLR_OFFSET) = (1u << shift);
    }
}

uint8_t gio_get_and_clear_int_flag(gio_port_t port, uint8_t pin) {
    uint32_t shift;
    uint32_t reg_val;
    uint8_t flag;

    shift = (uint32_t)port * 8u + pin;

    /* [prov] regs.yaml:GIO.GIOFLG */
    reg_val = REG32(GIO_BASE + GIOFLG_OFFSET);
    flag = (uint8_t)((reg_val >> shift) & 1u);

    /* Clear by writing 1 */
    if (flag != 0u) {
        REG32(GIO_BASE + GIOFLG_OFFSET) = (1u << shift);
    }

    return flag;
}

uint8_t gio_get_offset1(void) {
    /* [prov] regs.yaml:GIO.GIOOFF1 */
    return (uint8_t)(REG32(GIO_BASE + GIOOFF1_OFFSET) & 0x3Fu);
}

uint8_t gio_get_offset2(void) {
    /* [prov] regs.yaml:GIO.GIOOFF2 */
    return (uint8_t)(REG32(GIO_BASE + GIOOFF2_OFFSET) & 0x3Fu);
}

uint8_t gio_get_emu1(void) {
    /* [prov] regs.yaml:GIO.GIOEMU1 */
    return (uint8_t)(REG32(GIO_BASE + GIOEMU1_OFFSET) & 0x3Fu);
}

uint8_t gio_get_emu2(void) {
    /* [prov] regs.yaml:GIO.GIOEMU2 */
    return (uint8_t)(REG32(GIO_BASE + GIOEMU2_OFFSET) & 0x3Fu);
}

int gio_register_isr_a(gio_isr_t isr) {
    int ret;

    ret = vim_register_isr(GIO_IRQ_A_ID, isr);
    if (ret != 0) {
        return ret;
    }

    return vim_enable_channel(GIO_IRQ_A_ID);
}

int gio_register_isr_b(gio_isr_t isr) {
    int ret;

    ret = vim_register_isr(GIO_IRQ_B_ID, isr);
    if (ret != 0) {
        return ret;
    }

    return vim_enable_channel(GIO_IRQ_B_ID);
}

int gio_disable_irq_a(void) {
    return vim_disable_channel(GIO_IRQ_A_ID);
}

int gio_disable_irq_b(void) {
    return vim_disable_channel(GIO_IRQ_B_ID);
}