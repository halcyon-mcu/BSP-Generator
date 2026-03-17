/* BSP-GEN-META: created_at=2026-03-04T23:26:17-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file pcr_driver.c
 * @brief PCR (Peripheral Central Resource Controller) driver implementation
 * @details Complete implementation for power domain and clock domain control,
 *          including initialization and peripheral enable/disable functions.
 *          
 *          The PCR module controls power and clock distribution to peripheral
 *          domains through set/clear register pairs. This implementation uses
 *          clear registers for power-up (enabling) and set registers for
 *          power-down (disabling) operations.
 */

#include "pcr_driver.h"
#include "reg_pcr.h"
#include <stdint.h>
#include <stdbool.h>

/*===========================================================================*/
/* Module Base Address Definition                                           */
/*===========================================================================*/

/**
 * @brief PCR module base address
 */
#define PCR_BASE_ADDR (0xFFFFE000U)

/**
 * @brief PCR register map pointer
 */
#define PCR ((PCR_REG_MAP_t *)PCR_BASE_ADDR)

/*===========================================================================*/
/* Helper Macros                                                             */
/*===========================================================================*/

/**
 * @brief Maximum power domain number
 */
#define PCR_MAX_DOMAIN (31U)

/**
 * @brief Maximum clock domain number
 */
#define PCR_MAX_CLOCK_DOMAIN (31U)

/*===========================================================================*/
/* Public Function Implementations                                          */
/*===========================================================================*/

/**
 * @brief Initialize PCR module - powers up all peripheral domains
 * @details Executes power-up sequence using CLR registers to enable all
 *          peripheral power domains and clock domains. This brings the
 *          system to a fully-powered state where all peripherals can be
 *          accessed.
 *          
 *          Per hardware specification:
 *          - Writing 1 to PSPWRDWNCLRx enables power to that domain
 *          - Writing 1 to PCSPWRDWNCLRx enables clock to that domain
 *          
 * @note This function must be called during system initialization before
 *       accessing any peripheral registers.
 */
void PCR_Init(void)
{
    /* Power up all peripheral power domains (PS0-PS31) */
    PCR->PSPWRDWNCLR0 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR1 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR2 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR3 = 0xFFFFFFFFU;

    /* Enable clocks to all peripheral clock domains (PCS0-PCS31) */
    PCR->PCSPWRDWNCLR0 = 0xFFFFFFFFU;
    PCR->PCSPWRDWNCLR1 = 0xFFFFFFFFU;
}

/**
 * @brief Enable power to a specific peripheral power domain
 * @details Writes to the appropriate PSPWRDWNCLR register to enable power
 *          to the specified domain. Writing 1 to the corresponding bit
 *          brings the domain out of power-down state.
 *
 * @param domain Power domain to enable (PCR_DOMAIN_PS0 to PCR_DOMAIN_PS31)
 * @return pcr_status_t Status code
 * @retval PCR_STATUS_OK Power enabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Domain number out of valid range
 */
pcr_status_t PCR_EnablePeripheralPower(pcr_domain_t domain)
{
    uint32_t domain_num;
    volatile uint32_t *target_reg;
    uint32_t bit_mask;

    /* Validate domain range */
    domain_num = (uint32_t)domain;
    if (domain_num > PCR_MAX_DOMAIN) {
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Determine target register and bit position */
    if (domain_num < 32U) {
        /* Domains 0-31 map to PSPWRDWNCLR0 bits 0-31 */
        target_reg = &(PCR->PSPWRDWNCLR0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Enable power by writing to clear register */
    *target_reg = bit_mask;

    return PCR_STATUS_OK;
}

/**
 * @brief Disable power to a specific peripheral power domain
 * @details Writes to the appropriate PSPWRDWNSET register to disable power
 *          to the specified domain. Writing 1 to the corresponding bit
 *          puts the domain into power-down state.
 *
 * @param domain Power domain to disable (PCR_DOMAIN_PS0 to PCR_DOMAIN_PS31)
 * @return pcr_status_t Status code
 * @retval PCR_STATUS_OK Power disabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Domain number out of valid range
 */
pcr_status_t PCR_DisablePeripheralPower(pcr_domain_t domain)
{
    uint32_t domain_num;
    volatile uint32_t *target_reg;
    uint32_t bit_mask;

    /* Validate domain range */
    domain_num = (uint32_t)domain;
    if (domain_num > PCR_MAX_DOMAIN) {
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Determine target register and bit position */
    if (domain_num < 32U) {
        /* Domains 0-31 map to PSPWRDWNSET0 bits 0-31 */
        target_reg = &(PCR->PSPWRDWNSET0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Disable power by writing to set register */
    *target_reg = bit_mask;

    return PCR_STATUS_OK;
}

/**
 * @brief Enable clock to a specific peripheral clock domain
 * @details Writes to the appropriate PCSPWRDWNCLR register to enable clock
 *          to the specified domain. Writing 1 to the corresponding bit
 *          enables clock distribution to that domain.
 *
 * @param clock_domain Clock domain to enable (PCR_CLKDOMAIN_PCS0 to PCR_CLKDOMAIN_PCS31)
 * @return pcr_status_t Status code
 * @retval PCR_STATUS_OK Clock enabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Clock domain number out of valid range
 */
pcr_status_t PCR_EnablePeripheralClock(pcr_clock_domain_t clock_domain)
{
    uint32_t domain_num;
    volatile uint32_t *target_reg;
    uint32_t bit_mask;

    /* Validate clock domain range */
    domain_num = (uint32_t)clock_domain;
    if (domain_num > PCR_MAX_CLOCK_DOMAIN) {
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Determine target register and bit position */
    if (domain_num < 32U) {
        /* Clock domains 0-31 map to PCSPWRDWNCLR0 bits 0-31 */
        target_reg = &(PCR->PCSPWRDWNCLR0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Enable clock by writing to clear register */
    *target_reg = bit_mask;

    return PCR_STATUS_OK;
}

/**
 * @brief Disable clock to a specific peripheral clock domain
 * @details Writes to the appropriate PCSPWRDWNSET register to disable clock
 *          to the specified domain. Writing 1 to the corresponding bit
 *          disables clock distribution to that domain.
 *
 * @param clock_domain Clock domain to disable (PCR_CLKDOMAIN_PCS0 to PCR_CLKDOMAIN_PCS31)
 * @return pcr_status_t Status code
 * @retval PCR_STATUS_OK Clock disabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Clock domain number out of valid range
 */
pcr_status_t PCR_DisablePeripheralClock(pcr_clock_domain_t clock_domain)
{
    uint32_t domain_num;
    volatile uint32_t *target_reg;
    uint32_t bit_mask;

    /* Validate clock domain range */
    domain_num = (uint32_t)clock_domain;
    if (domain_num > PCR_MAX_CLOCK_DOMAIN) {
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Determine target register and bit position */
    if (domain_num < 32U) {
        /* Clock domains 0-31 map to PCSPWRDWNSET0 bits 0-31 */
        target_reg = &(PCR->PCSPWRDWNSET0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return PCR_STATUS_INVALID_DOMAIN;
    }

    /* Disable clock by writing to set register */
    *target_reg = bit_mask;

    return PCR_STATUS_OK;
}

/**
 * @brief Get the power status of a specific peripheral domain
 * @details Reads the appropriate PSPWRDWNSET register to determine if the
 *          domain is powered. A bit value of 0 indicates the domain is
 *          powered (active), while 1 indicates power-down state.
 *
 * @param domain Power domain to query (PCR_DOMAIN_PS0 to PCR_DOMAIN_PS31)
 * @return bool Power status
 * @retval true Domain is powered (active)
 * @retval false Domain is powered down or invalid domain number
 */
bool PCR_GetPeripheralPowerStatus(pcr_domain_t domain)
{
    uint32_t domain_num;
    volatile uint32_t *status_reg;
    uint32_t bit_mask;
    uint32_t reg_value;

    /* Validate domain range */
    domain_num = (uint32_t)domain;
    if (domain_num > PCR_MAX_DOMAIN) {
        return false;
    }

    /* Determine status register and bit position */
    if (domain_num < 32U) {
        /* Domains 0-31 status in PSPWRDWNSET0 bits 0-31 */
        status_reg = &(PCR->PSPWRDWNSET0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return false;
    }

    /* Read status register */
    reg_value = *status_reg;

    /* Return true if powered (bit is 0), false if powered down (bit is 1) */
    return ((reg_value & bit_mask) == 0U);
}

/**
 * @brief Get the clock status of a specific peripheral clock domain
 * @details Reads the appropriate PCSPWRDWNSET register to determine if the
 *          clock domain is enabled. A bit value of 0 indicates the clock
 *          is enabled (active), while 1 indicates clock is disabled.
 *
 * @param clock_domain Clock domain to query (PCR_CLKDOMAIN_PCS0 to PCR_CLKDOMAIN_PCS31)
 * @return bool Clock status
 * @retval true Clock is enabled (active)
 * @retval false Clock is disabled or invalid clock domain number
 */
bool PCR_GetPeripheralClockStatus(pcr_clock_domain_t clock_domain)
{
    uint32_t domain_num;
    volatile uint32_t *status_reg;
    uint32_t bit_mask;
    uint32_t reg_value;

    /* Validate clock domain range */
    domain_num = (uint32_t)clock_domain;
    if (domain_num > PCR_MAX_CLOCK_DOMAIN) {
        return false;
    }

    /* Determine status register and bit position */
    if (domain_num < 32U) {
        /* Clock domains 0-31 status in PCSPWRDWNSET0 bits 0-31 */
        status_reg = &(PCR->PCSPWRDWNSET0);
        bit_mask = (1U << domain_num);
    } else {
        /* Should not reach here due to validation above */
        return false;
    }

    /* Read status register */
    reg_value = *status_reg;

    /* Return true if clock enabled (bit is 0), false if disabled (bit is 1) */
    return ((reg_value & bit_mask) == 0U);
}

/**
 * @brief Enable all known PCR-controlled peripherals
 * @details Compatibility helper for startup ordering contract.
 */
void PCR_EnableAllPeripherals(void)
{
    /* Enable all PCR-controlled domains by clearing powerdown bits. */
    PCR->PSPWRDWNCLR0 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR1 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR2 = 0xFFFFFFFFU;
    PCR->PSPWRDWNCLR3 = 0xFFFFFFFFU;
}
