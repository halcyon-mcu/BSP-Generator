/* BSP-GEN-META: created_at=2026-03-04T23:26:36-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef GIO_DRIVER_H
#define GIO_DRIVER_H

/**
 * @file gio_driver.h
 * @brief Public API for GIO peripheral driver
 * @details Complete public interface for the GIO module including
 *          types, enumerations, structures, and function prototypes
 *          for GPIO configuration, control, and int_type management.
 */

#include <stdint.h>
#include <stdbool.h>
#include "reg_gio.h"

/**
 * @brief GIO operation status codes
 * @details Return values for GIO driver functions indicating
 *          success or various error conditions.
 */
typedef enum {
    GIO_STATUS_OK,            /**< Operation completed successfully */
    GIO_STATUS_ERROR,         /**< General error occurred */
    GIO_STATUS_INVALID_PIN,   /**< Invalid pin number specified */
    GIO_STATUS_INVALID_PORT   /**< Invalid port identifier specified */
} gio_status_t;

/**
 * @brief Pin direction configuration
 * @details Configures a GPIO pin as either input or output.
 */
typedef enum {
    GIO_DIRECTION_INPUT,   /**< Configure pin as input */
    GIO_DIRECTION_OUTPUT   /**< Configure pin as output */
} gio_direction_t;

/**
 * @brief Pin pull-up/pull-down configuration
 * @details Configures internal pull resistors for a GPIO pin.
 */
typedef enum {
    GIO_PULL_DISABLE,   /**< Disable pull resistors */
    GIO_PULL_DOWN,      /**< Enable pull-down resistor */
    GIO_PULL_UP         /**< Enable pull-up resistor */
} gio_pull_t;

/**
 * @brief Pin output drive mode
 * @details Configures the output driver type for a GPIO pin.
 */
typedef enum {
    GIO_DRIVE_PUSH_PULL,   /**< Push-pull output driver */
    GIO_DRIVE_OPEN_DRAIN   /**< Open-drain output driver */
} gio_drive_t;

/**
 * @brief Interrupt edge detection configuration
 * @details Configures which edge transitions trigger an int_type.
 */
typedef enum {
    GIO_INT_FALLING_EDGE,   /**< Trigger on falling edge */
    GIO_INT_RISING_EDGE,    /**< Trigger on rising edge */
    GIO_INT_BOTH_EDGES      /**< Trigger on both edges */
} gio_int_edge_t;

/**
 * @brief Interrupt level detection configuration
 * @details Configures which logic level triggers an int_type.
 */
typedef enum {
    GIO_INT_LEVEL_LOW,    /**< Trigger on low level */
    GIO_INT_LEVEL_HIGH    /**< Trigger on high level */
} gio_int_level_t;

/**
 * @brief GIO port identifier
 * @details Identifies which GPIO port to operate on.
 */
typedef enum {
    GIO_PORT_A,   /**< GPIO Port A */
    GIO_PORT_B    /**< GPIO Port B */
} gio_port_t;

/**
 * @brief Interrupt callback function pointer type
 * @details User-defined callback function invoked when a GPIO int_type occurs.
 *
 * @param[in] port GPIO port that generated the int_type
 * @param[in] pin Pin number that generated the int_type
 */
typedef void (*gio_interrupt_callback_t)(gio_port_t port, uint8_t pin);

/**
 * @brief Pin configuration structure
 * @details Complete configuration parameters for a single GPIO pin.
 */
typedef struct {
    gio_port_t port;              /**< Target GPIO port */
    uint8_t pin;                  /**< Pin number within the port */
    gio_direction_t direction;    /**< Pin direction (input/output) */
    gio_pull_t pull;              /**< Pull resistor configuration */
    gio_drive_t drive;            /**< Output drive mode */
    bool initial_value;           /**< Initial output value (for outputs) */
} gio_pin_config_t;

/**
 * @brief Interrupt configuration structure
 * @details Complete configuration parameters for GPIO int_type functionality.
 */
typedef struct {
    gio_port_t port;                      /**< Target GPIO port */
    uint8_t pin;                          /**< Pin number within the port */
    gio_int_edge_t edge;                  /**< Edge detection configuration */
    gio_int_level_t level;                /**< Level detection configuration */
    gio_interrupt_callback_t callback;    /**< User callback function */
} gio_interrupt_config_t;

/**
 * @brief Initialize the GIO module
 * @details Initializes the GIO peripheral, configures clock control register,
 *          and sets up default port configuration.
 *
 * @return Status of the initialization operation
 * @retval GIO_STATUS_OK Initialization completed successfully
 * @retval GIO_STATUS_ERROR Initialization failed
 */
gio_status_t GIO_Init(void);

/**
 * @brief Configure a single GPIO pin
 * @details Configures a GPIO pin with specified direction, pull resistors,
 *          drive mode, and initial output value.
 *
 * @param[in] config Pointer to pin configuration structure
 * @return Status of the configuration operation
 * @retval GIO_STATUS_OK Configuration successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 * @retval GIO_STATUS_ERROR Configuration failed
 */
gio_status_t GIO_ConfigurePin(const gio_pin_config_t* config);

/**
 * @brief Write a digital value to an output pin
 * @details Sets or clears the output state of a GPIO pin configured as output.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @param[in] value Logic level to write (true=high, false=low)
 * @return Status of the write operation
 * @retval GIO_STATUS_OK Write successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_WritePin(gio_port_t port, uint8_t pin, bool value);

/**
 * @brief Read the current state of a GPIO pin
 * @details Reads the current logic level of a GPIO pin.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @return Current pin state (true=high, false=low)
 */
bool GIO_ReadPin(gio_port_t port, uint8_t pin);

/**
 * @brief Toggle the output state of a GPIO pin
 * @details Inverts the current output state of a GPIO pin.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @return Status of the toggle operation
 * @retval GIO_STATUS_OK Toggle successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_TogglePin(gio_port_t port, uint8_t pin);

/**
 * @brief Write a 32-bit value to an entire GPIO port
 * @details Writes all pins of a GPIO port simultaneously.
 *
 * @param[in] port Target GPIO port
 * @param[in] value 32-bit value to write to the port
 * @return Status of the write operation
 * @retval GIO_STATUS_OK Write successful
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_WritePort(gio_port_t port, uint32_t value);

/**
 * @brief Read the current state of an entire GPIO port
 * @details Reads all pins of a GPIO port simultaneously.
 *
 * @param[in] port Target GPIO port
 * @return 32-bit value representing current port state
 */
uint32_t GIO_ReadPort(gio_port_t port);

/**
 * @brief Configure int_type settings for a GPIO pin
 * @details Sets up int_type parameters including edge/level detection
 *          and registers a user callback function.
 *
 * @param[in] config Pointer to int_type configuration structure
 * @return Status of the configuration operation
 * @retval GIO_STATUS_OK Configuration successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 * @retval GIO_STATUS_ERROR Configuration failed
 */
gio_status_t GIO_ConfigureInterrupt(const gio_interrupt_config_t* config);

/**
 * @brief Enable int_type for a specific GPIO pin
 * @details Enables int_type generation for the specified pin.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @return Status of the operation
 * @retval GIO_STATUS_OK Interrupt enabled successfully
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_EnableInterrupt(gio_port_t port, uint8_t pin);

/**
 * @brief Disable int_type for a specific GPIO pin
 * @details Disables int_type generation for the specified pin.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @return Status of the operation
 * @retval GIO_STATUS_OK Interrupt disabled successfully
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_DisableInterrupt(gio_port_t port, uint8_t pin);

/**
 * @brief Clear the int_type flag for a specific GPIO pin
 * @details Clears the pending int_type flag for the specified pin.
 *
 * @param[in] port Target GPIO port
 * @param[in] pin Pin number within the port
 * @return Status of the operation
 * @retval GIO_STATUS_OK Interrupt flag cleared successfully
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port identifier
 */
gio_status_t GIO_ClearInterruptFlag(gio_port_t port, uint8_t pin);

/**
 * @brief Get the int_type status register for a GPIO port
 * @details Reads the int_type status register showing which pins
 *          have pending interrupts.
 *
 * @param[in] port Target GPIO port
 * @return 32-bit int_type status register value
 */
uint32_t GIO_GetInterruptStatus(gio_port_t port);

void GIO_EnablePins(void);

#endif /* GIO_DRIVER_H */
