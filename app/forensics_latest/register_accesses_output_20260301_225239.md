# Register Access Ledger: register_accesses_output_20260301_225239.csv

- Total accesses: 104

| File | Function | Line | Access | Address | Op | Code |
|---|---|---:|---|---|---|---|
| source/pll_driver.c | PLL_ClearSlipStatus | 1002 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = SYSTEM_GLBSTAT_RFSLIP \| SYSTEM_GLBSTAT_FBSLIP; |
| source/pll_driver.c | PLL_ConfigurePLL | 596 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF; |
| source/pll_driver.c | PLL_ConfigurePLL | 599 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) != 0U) |
| source/pll_driver.c | PLL_ConfigurePLL | 608 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = pllctl1_value; |
| source/pll_driver.c | PLL_ConfigurePLL | 612 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = pllctl2_value; |
| source/pll_driver.c | PLL_ConfigurePLL | 615 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_ConfigurePLL | 623 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | PLL_ConfigurePLL | 626 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) != 0U) |
| source/pll_driver.c | PLL_ConfigurePLL | 635 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = pllctl1_value; |
| source/pll_driver.c | PLL_ConfigurePLL | 638 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | PLL_DisableClock | 506 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF; |
| source/pll_driver.c | PLL_DisableClock | 510 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | PLL_DisableClock | 514 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR5OFF; |
| source/pll_driver.c | PLL_DisableClock | 518 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR4OFF; |
| source/pll_driver.c | PLL_DisableClock | 522 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETGCLKOFF; |
| source/pll_driver.c | PLL_DisableClock | 526 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETHCLKOFF; |
| source/pll_driver.c | PLL_DisableClock | 530 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKPOFF; |
| source/pll_driver.c | PLL_DisableClock | 534 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK2OFF; |
| source/pll_driver.c | PLL_DisableClock | 538 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK3OFF; |
| source/pll_driver.c | PLL_DisableClock | 542 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK4OFF; |
| source/pll_driver.c | PLL_DisableClock | 546 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA1OFF; |
| source/pll_driver.c | PLL_DisableClock | 550 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA3OFF; |
| source/pll_driver.c | PLL_DisableClock | 554 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA4OFF; |
| source/pll_driver.c | PLL_DisableClock | 558 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETRTI1CLKOFF; |
| source/pll_driver.c | PLL_DisableClockMonitor | 985 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST &= ~SYSTEM_CLKTEST_RANGEDETCTRL; |
| source/pll_driver.c | PLL_DisableClockMonitor | 986 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST &= ~SYSTEM_CLKTEST_RANGEDETENASSEL; |
| source/pll_driver.c | PLL_EnableClock | 423 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_EnableClock | 427 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | PLL_EnableClock | 431 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR5OFF; |
| source/pll_driver.c | PLL_EnableClock | 435 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR4OFF; |
| source/pll_driver.c | PLL_EnableClock | 439 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF; |
| source/pll_driver.c | PLL_EnableClock | 443 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRHCLKOFF; |
| source/pll_driver.c | PLL_EnableClock | 447 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKPOFF; |
| source/pll_driver.c | PLL_EnableClock | 451 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK2OFF; |
| source/pll_driver.c | PLL_EnableClock | 455 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK3OFF; |
| source/pll_driver.c | PLL_EnableClock | 459 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK4OFF; |
| source/pll_driver.c | PLL_EnableClock | 463 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA1OFF; |
| source/pll_driver.c | PLL_EnableClock | 467 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA3OFF; |
| source/pll_driver.c | PLL_EnableClock | 471 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA4OFF; |
| source/pll_driver.c | PLL_EnableClock | 475 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRRTI1CLKOFF; |
| source/pll_driver.c | PLL_EnableClockMonitor | 967 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR5OFF; |
| source/pll_driver.c | PLL_EnableClockMonitor | 970 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST \|= SYSTEM_CLKTEST_RANGEDETCTRL; |
| source/pll_driver.c | PLL_EnableClockMonitor | 971 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST \|= SYSTEM_CLKTEST_RANGEDETENASSEL; |
| source/pll_driver.c | PLL_EnableOscillator | 835 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR0OFF; |
| source/pll_driver.c | PLL_EnableOscillator | 839 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR0V) == 0U)) |
| source/pll_driver.c | PLL_GetClockDivider | 937 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | divider = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetClockDivider | 941 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | divider = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT; |
| source/pll_driver.c | PLL_GetClockDivider | 945 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | divider = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK3R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT; |
| source/pll_driver.c | PLL_GetClockDivider | 949 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | divider = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK4R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 366 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 371 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclk2r = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 376 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | vclk3r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK3R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 381 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | vclk4r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK4R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 389 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetLockStatus | 752 | SYSREG->GLBSTAT | 0xFFFFFFEC | read | glbstat = SYSREG->GLBSTAT; |
| source/pll_driver.c | PLL_GetLockStatus | 768 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | if ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) != 0U) |
| source/pll_driver.c | PLL_GetLockStatus | 779 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | if ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) != 0U) |
| source/pll_driver.c | PLL_GetPLLFrequency | 675 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | if ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) == 0U) |
| source/pll_driver.c | PLL_GetPLLFrequency | 681 | SYSREG->PLLCTL1 | 0xFFFFFF70 | read | pllctl1 = SYSREG->PLLCTL1; |
| source/pll_driver.c | PLL_GetPLLFrequency | 682 | SYSREG->PLLCTL2 | 0xFFFFFF74 | read | pllctl2 = SYSREG->PLLCTL2; |
| source/pll_driver.c | PLL_GetPLLFrequency | 711 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | if ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) == 0U) |
| source/pll_driver.c | PLL_GetPLLFrequency | 717 | SYSREG2->PLLCTL3 | 0xFFFFE100 | read | pllctl1 = SYSREG2->PLLCTL3; |
| source/pll_driver.c | PLL_Init | 248 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF \| SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | PLL_Init | 251 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((SYSREG->CSVSTAT & HAL_ALIGNED_CSVSTAT_MASK) != 0U) |
| source/pll_driver.c | PLL_Init | 257 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = 0x00000301U; |
| source/pll_driver.c | PLL_Init | 261 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = 0x20000000U \| (0x1FU << 24U) \| ((PLL1_HAL_REFCLKDIV) << 16U) \| PLL1_HAL_ENCODED_PLLMUL; |
| source/pll_driver.c | PLL_Init | 264 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = (255U << 22U) \| (7U << 12U) \| ((2U - 1U) << 9U) \| 61U; |
| source/pll_driver.c | PLL_Init | 268 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = ((2U - 1U) << 29U) \| (0x1FU << 24U) \| ((6U - 1U) << 16U) \| PLL1_HAL_ENCODED_PLLMUL; |
| source/pll_driver.c | PLL_Init | 271 | SYSREG->CSDIS | 0xFFFFFF30 | write | SYSREG->CSDIS = HAL_ALIGNED_CSDIS; |
| source/pll_driver.c | PLL_Init | 272 | SYSREG->CDDIS | 0xFFFFFF3C | write | SYSREG->CDDIS = HAL_ALIGNED_CDDIS; |
| source/pll_driver.c | PLL_Init | 275 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR0OFF; |
| source/pll_driver.c | PLL_Init | 278 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF \| SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | PLL_Init | 297 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFU) \| (1U << 24U) \| (1U << 16U); |
| source/pll_driver.c | PLL_Init | 297 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFU) \| (1U << 24U) \| (1U << 16U); |
| source/pll_driver.c | PLL_Init | 300 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = GHVSRC_SOURCE_PLL1; |
| source/pll_driver.c | PLL_Init | 303 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = RCLKSRC_SYS_SOURCE_ID; |
| source/pll_driver.c | PLL_Init | 304 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = VCLKASRC_SYS_SOURCE_ID; |
| source/pll_driver.c | PLL_Init | 308 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = (1U << 8U) \| (1U << 0U); |
| source/pll_driver.c | PLL_Init | 312 | SYSREG2->VCLKACON1 | 0xFFFFE140 | write | SYSREG2->VCLKACON1 = (1U << 24U) \| (0U << 16U) \| (1U << 8U) \| (0U << 0U); |
| source/pll_driver.c | PLL_Init | 315 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF \| |
| source/pll_driver.c | PLL_Init | 321 | SYSREG->CLKCNTL | 0xFFFFFFD0 | rmw | SYSREG->CLKCNTL \|= SYSTEM_CLKCNTL_PENA; |
| source/pll_driver.c | PLL_SetClockDivider | 888 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | reg_value = SYSREG->CLKCNTL; |
| source/pll_driver.c | PLL_SetClockDivider | 891 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = reg_value; |
| source/pll_driver.c | PLL_SetClockDivider | 896 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | reg_value = SYSREG->CLKCNTL; |
| source/pll_driver.c | PLL_SetClockDivider | 899 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = reg_value; |
| source/pll_driver.c | PLL_SetClockDivider | 904 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | reg_value = SYSREG2->CLK2CNTRL; |
| source/pll_driver.c | PLL_SetClockDivider | 907 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = reg_value; |
| source/pll_driver.c | PLL_SetClockDivider | 912 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | reg_value = SYSREG2->CLK2CNTRL; |
| source/pll_driver.c | PLL_SetClockDivider | 915 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = reg_value; |
| source/pll_driver.c | calculate_hclk_frequency | 149 | SYSREG->GHVSRC | 0xFFFFFF48 | read | ghvsrc_source = (SYSREG->GHVSRC & SYSTEM_GHVSRC_GHVSRC_MASK) >> SYSTEM_GHVSRC_GHVSRC_SHIFT; |
| source/pll_driver.c | calculate_hclk_frequency | 158 | SYSREG->PLLCTL1 | 0xFFFFFF70 | read | pllctl1 = SYSREG->PLLCTL1; |
| source/pll_driver.c | calculate_hclk_frequency | 159 | SYSREG->PLLCTL2 | 0xFFFFFF74 | read | pllctl2 = SYSREG->PLLCTL2; |
| source/pll_driver.c | calculate_hclk_frequency | 194 | SYSREG2->PLLCTL3 | 0xFFFFE100 | read | pllctl1 = SYSREG2->PLLCTL3; |
| source/pll_driver.c | wait_for_pll1_lock | 86 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) == 0U)) |
| source/pll_driver.c | wait_for_pll2_lock | 112 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) == 0U)) |
| source/system.c | system_clear_status_flags | 101 | SYS->SYSESR | 0xFFFFFFE4 | write | SYS->SYSESR = SYS->SYSESR; |
| source/system.c | system_clear_status_flags | 101 | SYS->SYSESR | 0xFFFFFFE4 | write | SYS->SYSESR = SYS->SYSESR; |
| source/system.c | system_get_device_id | 94 | SYS->DEVID | 0xFFFFFFF0 | read | return SYS->DEVID; |
| source/system.c | system_get_reset_cause | 81 | SYS->SYSESR | 0xFFFFFFE4 | read | return SYS->SYSESR; |
| source/system.c | system_init | 60 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR \|= 0x0000000Au; |
| source/system.c | system_init | 63 | SYS->MSINENA | 0xFFFFFF60 | write | SYS->MSINENA = 0xFFFFFFFFu; |
| source/system.c | system_init | 66 | SYS->MSTCGSTAT | 0xFFFFFF68 | write | SYS->MSTCGSTAT = 0x00000100u; |
| source/system.c | system_init | 69 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR &= ~0x00000005u; |
| source/system.c | system_soft_reset | 88 | SYS->SYSECR | 0xFFFFFFE0 | write | SYS->SYSECR = 0x8000u; |
