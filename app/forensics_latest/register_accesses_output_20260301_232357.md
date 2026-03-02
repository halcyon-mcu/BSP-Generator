# Register Access Ledger: register_accesses_output_20260301_232357.csv

- Total accesses: 112

| File | Function | Line | Access | Address | Op | Code |
|---|---|---:|---|---|---|---|
| source/pll_driver.c | <global> | 978 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & csvstat_mask) == 0U)) |
| source/pll_driver.c | PLL_ClearSlipStatus | 1000 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = 0x00000301u; |
| source/pll_driver.c | PLL_ConfigurePLL | 639 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF; |
| source/pll_driver.c | PLL_ConfigurePLL | 645 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = pllctl1_value; |
| source/pll_driver.c | PLL_ConfigurePLL | 649 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = pllctl2_value; |
| source/pll_driver.c | PLL_ConfigurePLL | 652 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_DisableClock | 549 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF; |
| source/pll_driver.c | PLL_DisableClock | 553 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | PLL_DisableClock | 557 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR5OFF; |
| source/pll_driver.c | PLL_DisableClock | 561 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR4OFF; |
| source/pll_driver.c | PLL_DisableClock | 565 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETGCLKOFF; |
| source/pll_driver.c | PLL_DisableClock | 569 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETHCLKOFF; |
| source/pll_driver.c | PLL_DisableClock | 573 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKPOFF; |
| source/pll_driver.c | PLL_DisableClock | 577 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK2OFF; |
| source/pll_driver.c | PLL_DisableClock | 581 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK3OFF; |
| source/pll_driver.c | PLL_DisableClock | 585 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK4OFF; |
| source/pll_driver.c | PLL_DisableClock | 589 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA1OFF; |
| source/pll_driver.c | PLL_DisableClock | 593 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA3OFF; |
| source/pll_driver.c | PLL_DisableClock | 597 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA4OFF; |
| source/pll_driver.c | PLL_DisableClock | 601 | SYSREG->CDDISSET | 0xFFFFFF40 | write | SYSREG->CDDISSET = SYSTEM_CDDISSET_SETRTI1CLKOFF; |
| source/pll_driver.c | PLL_DisableClockMonitor | 1021 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST &= ~(SYSTEM_CLKTEST_RANGEDETENASSEL \| SYSTEM_CLKTEST_RANGEDETCTRL); |
| source/pll_driver.c | PLL_DisablePLL | 752 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF; |
| source/pll_driver.c | PLL_EnableClock | 469 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_EnableClock | 473 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | PLL_EnableClock | 477 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR5OFF; |
| source/pll_driver.c | PLL_EnableClock | 481 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR4OFF; |
| source/pll_driver.c | PLL_EnableClock | 485 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF; |
| source/pll_driver.c | PLL_EnableClock | 489 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRHCLKOFF; |
| source/pll_driver.c | PLL_EnableClock | 493 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKPOFF; |
| source/pll_driver.c | PLL_EnableClock | 497 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK2OFF; |
| source/pll_driver.c | PLL_EnableClock | 501 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK3OFF; |
| source/pll_driver.c | PLL_EnableClock | 505 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK4OFF; |
| source/pll_driver.c | PLL_EnableClock | 509 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA1OFF; |
| source/pll_driver.c | PLL_EnableClock | 513 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA3OFF; |
| source/pll_driver.c | PLL_EnableClock | 517 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA4OFF; |
| source/pll_driver.c | PLL_EnableClock | 521 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRRTI1CLKOFF; |
| source/pll_driver.c | PLL_EnableClockMonitor | 1012 | SYSREG->CLKTEST | 0xFFFFFF8C | rmw | SYSREG->CLKTEST \|= SYSTEM_CLKTEST_RANGEDETENASSEL \| SYSTEM_CLKTEST_RANGEDETCTRL; |
| source/pll_driver.c | PLL_EnablePLL | 730 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_GetClockSource | 840 | SYSREG->VCLKASRC | 0xFFFFFF4C | read | source_id = (SYSREG->VCLKASRC & SYSTEM_VCLKASRC_VCLKA1S_MASK) >> SYSTEM_VCLKASRC_VCLKA1S_SHIFT; |
| source/pll_driver.c | PLL_GetClockSource | 844 | SYSREG->RCLKSRC | 0xFFFFFF50 | read | source_id = (SYSREG->RCLKSRC & SYSTEM_RCLKSRC_RTI1SRC_MASK) >> SYSTEM_RCLKSRC_RTI1SRC_SHIFT; |
| source/pll_driver.c | PLL_GetDivider | 928 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | return (uint8_t)((SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT); |
| source/pll_driver.c | PLL_GetDivider | 931 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | return (uint8_t)((SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT); |
| source/pll_driver.c | PLL_GetDivider | 934 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | return (uint8_t)((SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK3R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT); |
| source/pll_driver.c | PLL_GetDivider | 937 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | return (uint8_t)((SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK4R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT); |
| source/pll_driver.c | PLL_GetFrequency | 413 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 417 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclk2r = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 421 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | vclk3r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK3R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 425 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | vclk4r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK4R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 431 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetFrequency | 437 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; |
| source/pll_driver.c | PLL_GetPLLStatus | 697 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | csvstat = SYSREG->CSVSTAT; |
| source/pll_driver.c | PLL_GetPLLStatus | 698 | SYSREG->GLBSTAT | 0xFFFFFFEC | read | glbstat = SYSREG->GLBSTAT; |
| source/pll_driver.c | PLL_Init | 260 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF \| SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | PLL_Init | 263 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = 0x00000301u; |
| source/pll_driver.c | PLL_Init | 266 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = PLL1_PLLCTL1_HAL_VALUE; |
| source/pll_driver.c | PLL_Init | 267 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = PLL1_PLLCTL2_HAL_VALUE; |
| source/pll_driver.c | PLL_Init | 270 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = PLL2_PLLCTL3_HAL_VALUE; |
| source/pll_driver.c | PLL_Init | 273 | SYSREG->CSDIS | 0xFFFFFF30 | write | SYSREG->CSDIS = HAL_CSDIS_VALUE; |
| source/pll_driver.c | PLL_Init | 274 | SYSREG->CDDIS | 0xFFFFFF3C | write | SYSREG->CDDIS = HAL_CDDIS_VALUE; |
| source/pll_driver.c | PLL_Init | 277 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; |
| source/pll_driver.c | PLL_Init | 286 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | PLL_Init | 299 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFu) \| (1u << 24u) \| (1u << 16u); |
| source/pll_driver.c | PLL_Init | 299 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFu) \| (1u << 24u) \| (1u << 16u); |
| source/pll_driver.c | PLL_Init | 302 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = (SYSREG->GHVSRC & ~SYSTEM_GHVSRC_GHVSRC_MASK) \| |
| source/pll_driver.c | PLL_Init | 302 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = (SYSREG->GHVSRC & ~SYSTEM_GHVSRC_GHVSRC_MASK) \| |
| source/pll_driver.c | PLL_Init | 306 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = (SYSREG->RCLKSRC & ~SYSTEM_RCLKSRC_RTI1SRC_MASK) \| |
| source/pll_driver.c | PLL_Init | 306 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = (SYSREG->RCLKSRC & ~SYSTEM_RCLKSRC_RTI1SRC_MASK) \| |
| source/pll_driver.c | PLL_Init | 310 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = (SYSREG->VCLKASRC & ~SYSTEM_VCLKASRC_VCLKA1S_MASK) \| |
| source/pll_driver.c | PLL_Init | 310 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = (SYSREG->VCLKASRC & ~SYSTEM_VCLKASRC_VCLKA1S_MASK) \| |
| source/pll_driver.c | PLL_Init | 317 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = (1u << SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT) \| |
| source/pll_driver.c | PLL_Init | 325 | SYSREG2->VCLKACON1 | 0xFFFFE140 | write | SYSREG2->VCLKACON1 = 0u; |
| source/pll_driver.c | PLL_Init | 328 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF \| |
| source/pll_driver.c | PLL_Init | 334 | SYSREG->CLKCNTL | 0xFFFFFFD0 | rmw | SYSREG->CLKCNTL \|= SYSTEM_CLKCNTL_PENA; |
| source/pll_driver.c | PLL_SetClockSource | 795 | SYSREG->GHVSRC | 0xFFFFFF48 | read | reg_value = SYSREG->GHVSRC; |
| source/pll_driver.c | PLL_SetClockSource | 798 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = reg_value; |
| source/pll_driver.c | PLL_SetClockSource | 803 | SYSREG->VCLKASRC | 0xFFFFFF4C | read | reg_value = SYSREG->VCLKASRC; |
| source/pll_driver.c | PLL_SetClockSource | 806 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = reg_value; |
| source/pll_driver.c | PLL_SetClockSource | 811 | SYSREG->RCLKSRC | 0xFFFFFF50 | read | reg_value = SYSREG->RCLKSRC; |
| source/pll_driver.c | PLL_SetClockSource | 814 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = reg_value; |
| source/pll_driver.c | PLL_SetDivider | 885 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | reg_value = SYSREG->CLKCNTL; |
| source/pll_driver.c | PLL_SetDivider | 888 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = reg_value; |
| source/pll_driver.c | PLL_SetDivider | 892 | SYSREG->CLKCNTL | 0xFFFFFFD0 | read | reg_value = SYSREG->CLKCNTL; |
| source/pll_driver.c | PLL_SetDivider | 895 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = reg_value; |
| source/pll_driver.c | PLL_SetDivider | 899 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | reg_value = SYSREG2->CLK2CNTRL; |
| source/pll_driver.c | PLL_SetDivider | 902 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = reg_value; |
| source/pll_driver.c | PLL_SetDivider | 906 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | read | reg_value = SYSREG2->CLK2CNTRL; |
| source/pll_driver.c | PLL_SetDivider | 909 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = reg_value; |
| source/pll_driver.c | calculate_hclk_from_pll1 | 172 | SYSREG->PLLCTL1 | 0xFFFFFF70 | read | pllctl1 = SYSREG->PLLCTL1; |
| source/pll_driver.c | calculate_hclk_from_pll1 | 173 | SYSREG->PLLCTL2 | 0xFFFFFF74 | read | pllctl2 = SYSREG->PLLCTL2; |
| source/pll_driver.c | get_active_ghvsrc_source | 215 | SYSREG->GHVSRC | 0xFFFFFF48 | read | ghvsrc_value = SYSREG->GHVSRC; |
| source/pll_driver.c | if | 660 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | if | 666 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = pllctl1_value; |
| source/pll_driver.c | if | 669 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | if | 735 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; |
| source/pll_driver.c | if | 757 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF; |
| source/pll_driver.c | wait_for_pll1_lock | 105 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) == 0U)) |
| source/pll_driver.c | wait_for_pll2_lock | 131 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((timeout > 0U) && ((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) == 0U)) |
| source/system.c | system_clear_status_flags | 139 | SYS->SYSESR | 0xFFFFFFE4 | write | SYS->SYSESR = SYS->SYSESR; |
| source/system.c | system_clear_status_flags | 139 | SYS->SYSESR | 0xFFFFFFE4 | write | SYS->SYSESR = SYS->SYSESR; |
| source/system.c | system_get_device_id | 129 | SYS->DEVID | 0xFFFFFFF0 | read | return SYS->DEVID; |
| source/system.c | system_get_reset_cause | 108 | SYS->SYSESR | 0xFFFFFFE4 | read | return SYS->SYSESR; |
| source/system.c | system_init | 76 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR \|= 0x0000000Au; |
| source/system.c | system_init | 80 | SYS->MSINENA | 0xFFFFFF60 | write | SYS->MSINENA = 0xFFFFFFFFu; |
| source/system.c | system_init | 84 | SYS->MSTCGSTAT | 0xFFFFFF68 | write | SYS->MSTCGSTAT = 0x00000100u; |
| source/system.c | system_init | 88 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR &= ~0x00000005u; |
| source/system.c | system_init | 97 | SYS->CLKCNTL | 0xFFFFFFD0 | rmw | SYS->CLKCNTL \|= (1u << 8u); |
| source/system.c | system_setup_flash_waitstates | 36 | FRDCNTL | 0xFFF87000 | write | *FRDCNTL = 0x00000311u; |
| source/system.c | system_setup_flash_waitstates | 39 | FSMWRENA | 0xFFF87288 | write | *FSMWRENA = 0x00000005u; |
| source/system.c | system_setup_flash_waitstates | 42 | EEPROMCONFIG | 0xFFF872B8 | write | *EEPROMCONFIG = 0x00030002u; |
| source/system.c | system_setup_flash_waitstates | 45 | FSMWRENA | 0xFFF87288 | write | *FSMWRENA = 0x0000000Au; |
| source/system.c | system_setup_flash_waitstates | 48 | FBFALLBACK | 0xFFF87040 | write | *FBFALLBACK = 0x00000000u; |
| source/system.c | system_soft_reset | 118 | SYS->SYSECR | 0xFFFFFFE0 | write | SYS->SYSECR = 0x8000u; |
