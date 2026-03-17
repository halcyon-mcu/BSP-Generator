/* BSP-GEN-META: created_at=2026-03-04T23:24:30-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_gio.h
 * @brief GIO Peripheral Register Map Header File
 * @details This file contains the register map structure and bit field definitions
 *          for the GIO (General-Purpose Input/Output) peripheral.
 * 
 * Base Address: 0xFFF7BC00
 */

#ifndef REG_GIO_H
#define REG_GIO_H

#include <stdint.h>

/**
 * @brief GIO Register Map Structure
 * @details Register map for GIO peripheral at base address 0xFFF7BC00
 */
typedef struct {
    volatile uint32_t GIOGCR0;      /**< 0x00: GIO Global Control Register */
    volatile uint32_t RESERVED0;    /**< 0x04: Reserved */
    volatile uint32_t GIOINTDET;    /**< 0x08: GIO Interrupt Detect Register */
    volatile uint32_t GIOPOL;       /**< 0x0C: GIO Interrupt Polarity Register */
    volatile uint32_t GIOENASET;    /**< 0x10: GIO Interrupt Enable Set Register */
    volatile uint32_t GIOENACLR;    /**< 0x14: GIO Interrupt Enable Clear Register */
    volatile uint32_t GIOLVLSET;    /**< 0x18: GIO Interrupt Priority Set Register */
    volatile uint32_t GIOLVLCLR;    /**< 0x1C: GIO Interrupt Priority Clear Register */
    volatile uint32_t GIOFLG;       /**< 0x20: GIO Interrupt Flag Register */
    volatile uint32_t GIOOFF1;      /**< 0x24: GIO Offset 1 Register */
    volatile uint32_t GIOOFF2;      /**< 0x28: GIO Offset 2 Register */
    volatile uint32_t GIOEMU1;      /**< 0x2C: GIO Emulation 1 Register */
    volatile uint32_t GIOEMU2;      /**< 0x30: GIO Emulation 2 Register */
    volatile uint32_t GIODIRA;      /**< 0x34: GIO Data Direction Register - Port A */
    volatile uint32_t GIODINA;      /**< 0x38: GIO Data Input Register - Port A */
    volatile uint32_t GIODOUTA;     /**< 0x3C: GIO Data Output Register - Port A */
    volatile uint32_t GIODSETA;     /**< 0x40: GIO Data Set Register - Port A */
    volatile uint32_t GIODCLRA;     /**< 0x44: GIO Data Clear Register - Port A */
    volatile uint32_t GIOPDRA;      /**< 0x48: GIO Open Drain Register - Port A */
    volatile uint32_t GIOPULDISA;   /**< 0x4C: GIO Pull Disable Register - Port A */
    volatile uint32_t GIOPSLA;      /**< 0x50: GIO Pull Select Register - Port A */
    volatile uint32_t GIODIRB;      /**< 0x54: GIO Data Direction Register - Port B */
    volatile uint32_t GIODINB;      /**< 0x58: GIO Data Input Register - Port B */
    volatile uint32_t GIODOUTB;     /**< 0x5C: GIO Data Output Register - Port B */
    volatile uint32_t GIODSETB;     /**< 0x60: GIO Data Set Register - Port B */
    volatile uint32_t GIODCLRB;     /**< 0x64: GIO Data Clear Register - Port B */
    volatile uint32_t GIOPDRB;      /**< 0x68: GIO Open Drain Register - Port B */
    volatile uint32_t GIOPULDISB;   /**< 0x6C: GIO Pull Disable Register - Port B */
    volatile uint32_t GIOPSLB;      /**< 0x70: GIO Pull Select Register - Port B */
} GIO_REG_MAP_t;

/* ========================================================================== */
/*                         GIOGCR0 Register Bit Masks                         */
/* ========================================================================== */
/** @brief GIO reset bit mask */
#define GIO_GIOGCR0_RESET                   (0x00000001u)

/* ========================================================================== */
/*                       GIOINTDET Register Bit Masks                         */
/* ========================================================================== */
/** @brief Interrupt detection select for pins GIOA[7:0] */
#define GIO_GIOINTDET_GIOINTDET0_MASK       (0x000000FFu)
#define GIO_GIOINTDET_GIOINTDET0_SHIFT      (0u)

/** @brief Interrupt detection select for pins GIOB[7:0] */
#define GIO_GIOINTDET_GIOINTDET1_MASK       (0x0000FF00u)
#define GIO_GIOINTDET_GIOINTDET1_SHIFT      (8u)

/** @brief Interrupt detection select for pins GIOC[7:0] */
#define GIO_GIOINTDET_GIOINTDET2_MASK       (0x00FF0000u)
#define GIO_GIOINTDET_GIOINTDET2_SHIFT      (16u)

/** @brief Interrupt detection select for pins GIOD[7:0] */
#define GIO_GIOINTDET_GIOINTDET3_MASK       (0xFF000000u)
#define GIO_GIOINTDET_GIOINTDET3_SHIFT      (24u)

/* ========================================================================== */
/*                        GIOPOL Register Bit Masks                           */
/* ========================================================================== */
/** @brief Interrupt polarity select for pins GIOA[7:0] */
#define GIO_GIOPOL_GIOPOL0_MASK             (0x000000FFu)
#define GIO_GIOPOL_GIOPOL0_SHIFT            (0u)

/** @brief Interrupt polarity select for pins GIOB[7:0] */
#define GIO_GIOPOL_GIOPOL1_MASK             (0x0000FF00u)
#define GIO_GIOPOL_GIOPOL1_SHIFT            (8u)

/** @brief Interrupt polarity select for pins GIOC[7:0] */
#define GIO_GIOPOL_GIOPOL2_MASK             (0x00FF0000u)
#define GIO_GIOPOL_GIOPOL2_SHIFT            (16u)

/** @brief Interrupt polarity select for pins GIOD[7:0] */
#define GIO_GIOPOL_GIOPOL3_MASK             (0xFF000000u)
#define GIO_GIOPOL_GIOPOL3_SHIFT            (24u)

/* ========================================================================== */
/*                       GIOENASET Register Bit Masks                         */
/* ========================================================================== */
/** @brief Interrupt enable for pins GIOA[7:0] */
#define GIO_GIOENASET_GIOENASET0_MASK       (0x000000FFu)
#define GIO_GIOENASET_GIOENASET0_SHIFT      (0u)

/** @brief Interrupt enable for pins GIOB[7:0] */
#define GIO_GIOENASET_GIOENASET1_MASK       (0x0000FF00u)
#define GIO_GIOENASET_GIOENASET1_SHIFT      (8u)

/** @brief Interrupt enable for pins GIOC[7:0] */
#define GIO_GIOENASET_GIOENASET2_MASK       (0x00FF0000u)
#define GIO_GIOENASET_GIOENASET2_SHIFT      (16u)

/** @brief Interrupt enable for pins GIOD[7:0] */
#define GIO_GIOENASET_GIOENASET3_MASK       (0xFF000000u)
#define GIO_GIOENASET_GIOENASET3_SHIFT      (24u)

/* ========================================================================== */
/*                       GIOENACLR Register Bit Masks                         */
/* ========================================================================== */
/** @brief Interrupt disable for pins GIOA[7:0] */
#define GIO_GIOENACLR_GIOENACLR0_MASK       (0x000000FFu)
#define GIO_GIOENACLR_GIOENACLR0_SHIFT      (0u)

/** @brief Interrupt disable for pins GIOB[7:0] */
#define GIO_GIOENACLR_GIOENACLR1_MASK       (0x0000FF00u)
#define GIO_GIOENACLR_GIOENACLR1_SHIFT      (8u)

/** @brief Interrupt disable for pins GIOC[7:0] */
#define GIO_GIOENACLR_GIOENACLR2_MASK       (0x00FF0000u)
#define GIO_GIOENACLR_GIOENACLR2_SHIFT      (16u)

/** @brief Interrupt disable for pins GIOD[7:0] */
#define GIO_GIOENACLR_GIOENACLR3_MASK       (0xFF000000u)
#define GIO_GIOENACLR_GIOENACLR3_SHIFT      (24u)

/* ========================================================================== */
/*                       GIOLVLSET Register Bit Masks                         */
/* ========================================================================== */
/** @brief GIO high-priority interrupt for pins GIOA[7:0] */
#define GIO_GIOLVLSET_GIOLVLSET0_MASK       (0x000000FFu)
#define GIO_GIOLVLSET_GIOLVLSET0_SHIFT      (0u)

/** @brief GIO high-priority interrupt for pins GIOB[7:0] */
#define GIO_GIOLVLSET_GIOLVLSET1_MASK       (0x0000FF00u)
#define GIO_GIOLVLSET_GIOLVLSET1_SHIFT      (8u)

/** @brief GIO high-priority interrupt for pins GIOC[7:0] */
#define GIO_GIOLVLSET_GIOLVLSET2_MASK       (0x00FF0000u)
#define GIO_GIOLVLSET_GIOLVLSET2_SHIFT      (16u)

/** @brief GIO high-priority interrupt for pins GIOD[7:0] */
#define GIO_GIOLVLSET_GIOLVLSET3_MASK       (0xFF000000u)
#define GIO_GIOLVLSET_GIOLVLSET3_SHIFT      (24u)

/* ========================================================================== */
/*                       GIOLVLCLR Register Bit Masks                         */
/* ========================================================================== */
/** @brief GIO low-priority interrupt for pins GIOA[7:0] */
#define GIO_GIOLVLCLR_GIOLVLCLR0_MASK       (0x000000FFu)
#define GIO_GIOLVLCLR_GIOLVLCLR0_SHIFT      (0u)

/** @brief GIO low-priority interrupt for pins GIOB[7:0] */
#define GIO_GIOLVLCLR_GIOLVLCLR1_MASK       (0x0000FF00u)
#define GIO_GIOLVLCLR_GIOLVLCLR1_SHIFT      (8u)

/** @brief GIO low-priority interrupt for pins GIOC[7:0] */
#define GIO_GIOLVLCLR_GIOLVLCLR2_MASK       (0x00FF0000u)
#define GIO_GIOLVLCLR_GIOLVLCLR2_SHIFT      (16u)

/** @brief GIO low-priority interrupt for pins GIOD[7:0] */
#define GIO_GIOLVLCLR_GIOLVLCLR3_MASK       (0xFF000000u)
#define GIO_GIOLVLCLR_GIOLVLCLR3_SHIFT      (24u)

/* ========================================================================== */
/*                        GIOFLG Register Bit Masks                           */
/* ========================================================================== */
/** @brief GIO flag for pins GIOA[7:0] */
#define GIO_GIOFLG_GIOFLG0_MASK             (0x000000FFu)
#define GIO_GIOFLG_GIOFLG0_SHIFT            (0u)

/** @brief GIO flag for pins GIOB[7:0] */
#define GIO_GIOFLG_GIOFLG1_MASK             (0x0000FF00u)
#define GIO_GIOFLG_GIOFLG1_SHIFT            (8u)

/** @brief GIO flag for pins GIOC[7:0] */
#define GIO_GIOFLG_GIOFLG2_MASK             (0x00FF0000u)
#define GIO_GIOFLG_GIOFLG2_SHIFT            (16u)

/** @brief GIO flag for pins GIOD[7:0] */
#define GIO_GIOFLG_GIOFLG3_MASK             (0xFF000000u)
#define GIO_GIOFLG_GIOFLG3_SHIFT            (24u)

/* ========================================================================== */
/*                        GIOOFF1 Register Bit Masks                          */
/* ========================================================================== */
/** @brief GIO offset 1 */
#define GIO_GIOOFF1_GIOOFF1_MASK            (0x0000003Fu)
#define GIO_GIOOFF1_GIOOFF1_SHIFT           (0u)

/* ========================================================================== */
/*                        GIOOFF2 Register Bit Masks                          */
/* ========================================================================== */
/** @brief GIO offset 2 */
#define GIO_GIOOFF2_GIOOFF2_MASK            (0x0000003Fu)
#define GIO_GIOOFF2_GIOOFF2_SHIFT           (0u)

/* ========================================================================== */
/*                        GIOEMU1 Register Bit Masks                          */
/* ========================================================================== */
/** @brief GIO offset emulation 1 */
#define GIO_GIOEMU1_GIOEMU1_MASK            (0x0000003Fu)
#define GIO_GIOEMU1_GIOEMU1_SHIFT           (0u)

/* ========================================================================== */
/*                        GIOEMU2 Register Bit Masks                          */
/* ========================================================================== */
/** @brief GIO offset emulation 2 */
#define GIO_GIOEMU2_GIOEMU2_MASK            (0x0000003Fu)
#define GIO_GIOEMU2_GIOEMU2_SHIFT           (0u)

/* ========================================================================== */
/*                     GIODIRA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO data direction of port A, pins [7:0] */
#define GIO_GIODIRA_GIODIR_MASK             (0x000000FFu)
#define GIO_GIODIRA_GIODIR_SHIFT            (0u)

/* ========================================================================== */
/*                     GIODINA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO data input for port A, pins [7:0] */
#define GIO_GIODINA_GIODIN_MASK             (0x000000FFu)
#define GIO_GIODINA_GIODIN_SHIFT            (0u)

/* ========================================================================== */
/*                    GIODOUTA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO data output of port A, pins[7:0] */
#define GIO_GIODOUTA_GIODOUT_MASK           (0x000000FFu)
#define GIO_GIODOUTA_GIODOUT_SHIFT          (0u)

/* ========================================================================== */
/*                    GIODSETA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO data set for port A, pins[7:0] */
#define GIO_GIODSETA_GIODSET_MASK           (0x000000FFu)
#define GIO_GIODSETA_GIODSET_SHIFT          (0u)

/* ========================================================================== */
/*                    GIODCLRA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO data clear for port A, pins[7:0] */
#define GIO_GIODCLRA_GIODCLR_MASK           (0x000000FFu)
#define GIO_GIODCLRA_GIODCLR_SHIFT          (0u)

/* ========================================================================== */
/*                     GIOPDRA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO open drain for port A, pins[7:0] */
#define GIO_GIOPDRA_GIOPDR_MASK             (0x000000FFu)
#define GIO_GIOPDRA_GIOPDR_SHIFT            (0u)

/* ========================================================================== */
/*                   GIOPULDISA Register Bit Masks (Port A)                   */
/* ========================================================================== */
/** @brief GIO pull disable for port A, pins[7:0] */
#define GIO_GIOPULDISA_GIOPULDIS_MASK       (0x000000FFu)
#define GIO_GIOPULDISA_GIOPULDIS_SHIFT      (0u)

/* ========================================================================== */
/*                     GIOPSLA Register Bit Masks (Port A)                    */
/* ========================================================================== */
/** @brief GIO pull select for port A, pins[7:0] */
#define GIO_GIOPSLA_GIOPSL_MASK             (0x000000FFu)
#define GIO_GIOPSLA_GIOPSL_SHIFT            (0u)

/* ========================================================================== */
/*                     GIODIRB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO data direction of port B, pins [7:0] */
#define GIO_GIODIRB_GIODIR_MASK             (0x000000FFu)
#define GIO_GIODIRB_GIODIR_SHIFT            (0u)

/* ========================================================================== */
/*                     GIODINB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO data input for port B, pins [7:0] */
#define GIO_GIODINB_GIODIN_MASK             (0x000000FFu)
#define GIO_GIODINB_GIODIN_SHIFT            (0u)

/* ========================================================================== */
/*                    GIODOUTB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO data output of port B, pins[7:0] */
#define GIO_GIODOUTB_GIODOUT_MASK           (0x000000FFu)
#define GIO_GIODOUTB_GIODOUT_SHIFT          (0u)

/* ========================================================================== */
/*                    GIODSETB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO data set for port B, pins[7:0] */
#define GIO_GIODSETB_GIODSET_MASK           (0x000000FFu)
#define GIO_GIODSETB_GIODSET_SHIFT          (0u)

/* ========================================================================== */
/*                    GIODCLRB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO data clear for port B, pins[7:0] */
#define GIO_GIODCLRB_GIODCLR_MASK           (0x000000FFu)
#define GIO_GIODCLRB_GIODCLR_SHIFT          (0u)

/* ========================================================================== */
/*                     GIOPDRB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO open drain for port B, pins[7:0] */
#define GIO_GIOPDRB_GIOPDR_MASK             (0x000000FFu)
#define GIO_GIOPDRB_GIOPDR_SHIFT            (0u)

/* ========================================================================== */
/*                   GIOPULDISB Register Bit Masks (Port B)                   */
/* ========================================================================== */
/** @brief GIO pull disable for port B, pins[7:0] */
#define GIO_GIOPULDISB_GIOPULDIS_MASK       (0x000000FFu)
#define GIO_GIOPULDISB_GIOPULDIS_SHIFT      (0u)

/* ========================================================================== */
/*                     GIOPSLB Register Bit Masks (Port B)                    */
/* ========================================================================== */
/** @brief GIO pull select for port B, pins[7:0] */
#define GIO_GIOPSLB_GIOPSL_MASK             (0x000000FFu)
#define GIO_GIOPSLB_GIOPSL_SHIFT            (0u)

#endif /* REG_GIO_H */
