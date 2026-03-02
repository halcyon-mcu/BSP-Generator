# SYSTEM + PLL Init Canonical Sequence (Working Bring-up)

This file captures the exact ordered register operations that restored terminal output.
Use it as the source of truth for `soc.yaml` `x-ext.init` content.

## SYSTEM.x-ext.init (ordered)
1. CLKCNTL set_bits 0x00000100 (0xFFFFFFD0)
2. CLKCNTL write 0x00010000 (0xFFFFFFD0)
3. MINITGCR set_bits 0x0000000A (0xFFFFFF5C)
4. MSINENA write 0xFFFFFFFF (0xFFFFFF60)
5. MSTCGSTAT write 0x00000100 (0xFFFFFF68)
6. MINITGCR clear_bits 0x00000005 (0xFFFFFF5C)
7. CSVSTAT write 0x00000000 (0xFFFFFF54)

## PLL.x-ext.init (ordered)
1. CSDISSET set_bits 0x00000042 (0xFFFFFF34)
2. GLBSTAT write 0x00000301 (0xFFFFFFEC)
3. PLLCTL1 write 0x3F05A400 (0xFFFFFF70)
4. PLLCTL2 write 0x3FC0723D (0xFFFFFF74)
5. PLLCTL3 write 0x3F05A400 (0xFFFFE100)
6. CSDIS write 0x0000008C (0xFFFFFF30)
7. CDDIS write 0x00000020 (0xFFFFFF3C)
8. GHVSRC write 0x00000001 (0xFFFFFF48)
9. RCLKSRC write 0x01090109 (0xFFFFFF50)
10. VCLKASRC write 0x00000909 (0xFFFFFF4C)
11. CLKCNTL write (SYSREG->CLKCNTL & 0xF0FFFFFFU) | (1U << 24U) (0xFFFFFFD0)
12. CLKCNTL write (SYSREG->CLKCNTL & 0xFFF0FFFFU) | (1U << 16U) (0xFFFFFFD0)
13. CLK2CNTRL write (SYSREG2->CLK2CNTRL & 0xFFFFF0F0U) | (1U << 8U) | (1U << 0U) (0xFFFFE13C)
14. VCLKACON1 write 0x00020002 (0xFFFFE140)
15. PLLCTL1 clear_bits 0x1F000000 (0xFFFFFF70)
16. PLLCTL3 clear_bits 0x1F000000 (0xFFFFE100)
17. CLKCNTL set_bits 0x00000100 (0xFFFFFFD0)

## Snippet Files
- app/yaml_in/system_init_exact_soc_snippet.yaml
- app/yaml_in/pll_init_exact_soc_snippet.yaml
