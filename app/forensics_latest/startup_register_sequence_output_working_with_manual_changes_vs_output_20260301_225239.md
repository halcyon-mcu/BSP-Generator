# Startup Register Access Sequence Comparison

- Working: `output_working_with_manual_changes`
- Target: `output_20260301_225239`

| Index | Working | Target | Match |
|---:|---|---|:---:|
| 1 | system_init | system.c:47 | SYS->CLKCNTL | 0xFFFFFFD0 | rmw | SYS->CLKCNTL |= 0x00000100u; | system_init | system.c:60 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR |= 0x0000000Au; | No |
| 2 | system_init | system.c:50 | SYS->CLKCNTL | 0xFFFFFFD0 | write | SYS->CLKCNTL = 0x00010000u; | system_init | system.c:63 | SYS->MSINENA | 0xFFFFFF60 | write | SYS->MSINENA = 0xFFFFFFFFu; | No |
| 3 | system_init | system.c:53 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR |= 0x0000000Au; | system_init | system.c:66 | SYS->MSTCGSTAT | 0xFFFFFF68 | write | SYS->MSTCGSTAT = 0x00000100u; | No |
| 4 | system_init | system.c:56 | SYS->MSINENA | 0xFFFFFF60 | write | SYS->MSINENA = 0xFFFFFFFFu; | system_init | system.c:69 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR &= ~0x00000005u; | No |
| 5 | system_init | system.c:59 | SYS->MSTCGSTAT | 0xFFFFFF68 | write | SYS->MSTCGSTAT = 0x00000100u; | PLL_Init | pll_driver.c:248 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF | SYSTEM_CSDISSET_SETCLKSR6OFF; | No |
| 6 | system_init | system.c:62 | SYS->MINITGCR | 0xFFFFFF5C | rmw | SYS->MINITGCR &= ~0x00000005u; | PLL_Init | pll_driver.c:251 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | while ((SYSREG->CSVSTAT & HAL_ALIGNED_CSVSTAT_MASK) != 0U) | No |
| 7 | system_init | system.c:68 | SYS->CSVSTAT | 0xFFFFFF54 | write | SYS->CSVSTAT = 0x00000000u; | PLL_Init | pll_driver.c:257 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = 0x00000301U; | No |
| 8 | PLL_Init | pll_driver.c:145 | SYSREG->CSDISSET | 0xFFFFFF34 | write | SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF | SYSTEM_CSDISSET_SETCLKSR6OFF; | PLL_Init | pll_driver.c:261 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = 0x20000000U | (0x1FU << 24U) | ((PLL1_HAL_REFCLKDIV) << 16U) | PLL1_HAL_ENCODED_PLLMUL; | No |
| 9 | PLL_Init | pll_driver.c:149 | SYSREG->CSDIS | 0xFFFFFF30 | read | g_pll_wait1_last_csdis = SYSREG->CSDIS; | PLL_Init | pll_driver.c:264 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = (255U << 22U) | (7U << 12U) | ((2U - 1U) << 9U) | 61U; | No |
| 10 | PLL_Init | pll_driver.c:157 | SYSREG->CSDIS | 0xFFFFFF30 | read | if ((SYSREG->CSDIS & csdis_target) != csdis_target) { | PLL_Init | pll_driver.c:268 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = ((2U - 1U) << 29U) | (0x1FU << 24U) | ((6U - 1U) << 16U) | PLL1_HAL_ENCODED_PLLMUL; | No |
| 11 | PLL_Init | pll_driver.c:158 | SYSREG->CSDIS | 0xFFFFFF30 | rmw | SYSREG->CSDIS |= csdis_target; | PLL_Init | pll_driver.c:271 | SYSREG->CSDIS | 0xFFFFFF30 | write | SYSREG->CSDIS = HAL_ALIGNED_CSDIS; | No |
| 12 | PLL_Init | pll_driver.c:162 | SYSREG->GLBSTAT | 0xFFFFFFEC | write | SYSREG->GLBSTAT = 0x00000301U; | PLL_Init | pll_driver.c:272 | SYSREG->CDDIS | 0xFFFFFF3C | write | SYSREG->CDDIS = HAL_ALIGNED_CDDIS; | No |
| 13 | PLL_Init | pll_driver.c:165 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = 0x20000000U | (0x1FU << 24U) | ((6U - 1U) << 16U) | 0xA400U; | PLL_Init | pll_driver.c:275 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR0OFF; | No |
| 14 | PLL_Init | pll_driver.c:166 | SYSREG->PLLCTL2 | 0xFFFFFF74 | write | SYSREG->PLLCTL2 = (255U << 22U) | (7U << 12U) | ((2U - 1U) << 9U) | 61U; | PLL_Init | pll_driver.c:278 | SYSREG->CSDISCLR | 0xFFFFFF38 | write | SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF | SYSTEM_CSDISCLR_CLRCLKSR6OFF; | No |
| 15 | PLL_Init | pll_driver.c:167 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = ((2U - 1U) << 29U) | (0x1FU << 24U) | ((6U - 1U) << 16U) | 0xA400U; | PLL_Init | pll_driver.c:297 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFU) | (1U << 24U) | (1U << 16U); | No |
| 16 | PLL_Init | pll_driver.c:169 | SYSREG->CSDIS | 0xFFFFFF30 | write | SYSREG->CSDIS = 0x0000008CU; | PLL_Init | pll_driver.c:297 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFU) | (1U << 24U) | (1U << 16U); | No |
| 17 | PLL_Init | pll_driver.c:170 | SYSREG->CDDIS | 0xFFFFFF3C | write | SYSREG->CDDIS = 0x00000020U; | PLL_Init | pll_driver.c:300 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = GHVSRC_SOURCE_PLL1; | No |
| 18 | PLL_Init | pll_driver.c:173 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | sys_csvstat = SYSREG->CSVSTAT; | PLL_Init | pll_driver.c:303 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = RCLKSRC_SYS_SOURCE_ID; | No |
| 19 | PLL_Init | pll_driver.c:174 | SYSREG->CSDIS | 0xFFFFFF30 | read | sys_csdis = SYSREG->CSDIS; | PLL_Init | pll_driver.c:304 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = VCLKASRC_SYS_SOURCE_ID; | No |
| 20 | PLL_Init | pll_driver.c:185 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | sys_csvstat = SYSREG->CSVSTAT; | PLL_Init | pll_driver.c:308 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = (1U << 8U) | (1U << 0U); | No |
| 21 | PLL_Init | pll_driver.c:186 | SYSREG->CSDIS | 0xFFFFFF30 | read | sys_csdis = SYSREG->CSDIS; | PLL_Init | pll_driver.c:312 | SYSREG2->VCLKACON1 | 0xFFFFE140 | write | SYSREG2->VCLKACON1 = (1U << 24U) | (0U << 16U) | (1U << 8U) | (0U << 0U); | No |
| 22 | PLL_Init | pll_driver.c:192 | SYSREG->GHVSRC | 0xFFFFFF48 | write | SYSREG->GHVSRC = (0U << 24U) | (0U << 16U) | (1U << 0U); | PLL_Init | pll_driver.c:315 | SYSREG->CDDISCLR | 0xFFFFFF44 | write | SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF | | No |
| 23 | PLL_Init | pll_driver.c:193 | SYSREG->RCLKSRC | 0xFFFFFF50 | write | SYSREG->RCLKSRC = (1U << 24U) | (RM46_SYS_VCLK_SOURCE << 16U) | | PLL_Init | pll_driver.c:321 | SYSREG->CLKCNTL | 0xFFFFFFD0 | rmw | SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA; | No |
| 24 | PLL_Init | pll_driver.c:195 | SYSREG->VCLKASRC | 0xFFFFFF4C | write | SYSREG->VCLKASRC = (RM46_SYS_VCLK_SOURCE << 8U) | (RM46_SYS_VCLK_SOURCE << 0U); |  | No |
| 25 | PLL_Init | pll_driver.c:198 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0FFFFFFU) | (1U << 24U); |  | No |
| 26 | PLL_Init | pll_driver.c:198 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0FFFFFFU) | (1U << 24U); |  | No |
| 27 | PLL_Init | pll_driver.c:199 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xFFF0FFFFU) | (1U << 16U); |  | No |
| 28 | PLL_Init | pll_driver.c:199 | SYSREG->CLKCNTL | 0xFFFFFFD0 | write | SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xFFF0FFFFU) | (1U << 16U); |  | No |
| 29 | PLL_Init | pll_driver.c:200 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = (SYSREG2->CLK2CNTRL & 0xFFFFF0F0U) | (1U << 8U) | (1U << 0U); |  | No |
| 30 | PLL_Init | pll_driver.c:200 | SYSREG2->CLK2CNTRL | 0xFFFFE13C | write | SYSREG2->CLK2CNTRL = (SYSREG2->CLK2CNTRL & 0xFFFFF0F0U) | (1U << 8U) | (1U << 0U); |  | No |
| 31 | PLL_Init | pll_driver.c:201 | SYSREG2->VCLKACON1 | 0xFFFFE140 | write | SYSREG2->VCLKACON1 = ((1U - 1U) << 24U) | (0U << 20U) | (2U << 16U) | |  | No |
| 32 | PLL_Init | pll_driver.c:204 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = (SYSREG->PLLCTL1 & 0xE0FFFFFFU) | ((1U - 1U) << 24U); |  | No |
| 33 | PLL_Init | pll_driver.c:204 | SYSREG->PLLCTL1 | 0xFFFFFF70 | write | SYSREG->PLLCTL1 = (SYSREG->PLLCTL1 & 0xE0FFFFFFU) | ((1U - 1U) << 24U); |  | No |
| 34 | PLL_Init | pll_driver.c:205 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = (SYSREG2->PLLCTL3 & 0xE0FFFFFFU) | ((1U - 1U) << 24U); |  | No |
| 35 | PLL_Init | pll_driver.c:205 | SYSREG2->PLLCTL3 | 0xFFFFE100 | write | SYSREG2->PLLCTL3 = (SYSREG2->PLLCTL3 & 0xE0FFFFFFU) | ((1U - 1U) << 24U); |  | No |
| 36 | PLL_Init | pll_driver.c:207 | SYSREG->PLLCTL2 | 0xFFFFFF74 | rmw | SYSREG->PLLCTL2 |= 0x00000000U; |  | No |
| 37 | PLL_Init | pll_driver.c:208 | SYSREG->CLKCNTL | 0xFFFFFFD0 | rmw | SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA; |  | No |
| 38 | PLL_Init | pll_driver.c:211 | SYSREG->CSVSTAT | 0xFFFFFF54 | read | csvstat = SYSREG->CSVSTAT; |  | No |
| 39 | main | main.c:157 | (volatile*) | 0xFFFFFF48 | read | g_dbg_ghvsrc = (*((volatile uint32_t *)0xFFFFFF48U)) & 0xFU; |  | No |
