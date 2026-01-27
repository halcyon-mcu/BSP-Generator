/* Stub clock.h for reference only */
#ifndef CLOCK_H
#define CLOCK_H

#include <stdint.h>

typedef enum {
    CLOCKREF_VCLK = 0
} clock_ref_t;

int clock_enable(clock_ref_t ref);
uint32_t clock_get_hz(clock_ref_t ref);

#endif
