/* Stub vim.h for reference only */
#ifndef VIM_H
#define VIM_H

#include <stdint.h>

int vim_register_isr(uint32_t channel_id, void (*isr)(void));
int vim_enable_channel(uint32_t channel_id);
int vim_disable_channel(uint32_t channel_id);

#endif
