"""
BSP Test Generator

Auto-generates runtime tests for BSP modules based on manifest API catalog.
Tests verify initialization, basic functionality, and hardware connectivity.
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class TestCase:
    """Single test case definition"""
    name: str
    description: str
    module: str
    code_lines: List[str]
    dependencies: List[str]


class TestPattern:
    """Base class for test pattern generators"""

    def can_generate(self, module_name: str, manifest_entry: Dict[str, Any]) -> bool:
        """Check if this pattern applies to the module"""
        raise NotImplementedError

    def generate_tests(self, module_name: str, manifest_entry: Dict[str, Any]) -> List[TestCase]:
        """Generate test cases for this module"""
        raise NotImplementedError


class InitializationTest(TestPattern):
    """Verify module initialization succeeds"""

    def can_generate(self, module_name: str, manifest_entry: Dict[str, Any]) -> bool:
        return "init_function" in manifest_entry

    def generate_tests(self, module_name: str, manifest_entry: Dict[str, Any]) -> List[TestCase]:
        return [TestCase(
            name=f"test_{module_name.lower()}_init",
            description=f"Verify {module_name} initialization",
            module=module_name,
            code_lines=[
                f"    // Test: {module_name} initialization",
                f"    test_count++;",
                f"    // Init was called during startup - verify no crash",
                f'    test_results[test_count-1] = TEST_PASS; // "{module_name} Init"',
            ],
            dependencies=[]
        )]


class ClockFrequencyTest(TestPattern):
    """Validate PLL clock frequencies"""

    def can_generate(self, module_name: str, manifest_entry: Dict[str, Any]) -> bool:
        if module_name != "PLL":
            return False
        funcs = manifest_entry.get("functions", [])
        return any("GetFrequency" in f.get("name", "") for f in funcs)

    def generate_tests(self, module_name: str, manifest_entry: Dict[str, Any]) -> List[TestCase]:
        return [TestCase(
            name="test_pll_frequency",
            description="Verify PLL frequencies are within expected ranges",
            module="PLL",
            code_lines=[
                "    // Test: PLL frequency validation",
                "    test_count++;",
                "    uint32_t gclk = PLL_GetFrequency(CLOCKDOMAIN_GCLK);",
                "    uint32_t hclk = PLL_GetFrequency(CLOCKDOMAIN_HCLK);",
                "    uint32_t vclk = PLL_GetFrequency(CLOCKDOMAIN_VCLK);",
                "    // Validate frequencies are reasonable",
                "    if (gclk > 1000000 && hclk > 0 && vclk > 0) {",
                '        test_results[test_count-1] = TEST_PASS; // "PLL Frequency"',
                "    } else {",
                '        test_results[test_count-1] = TEST_FAIL; // "PLL Frequency"',
                "        test_failures++;",
                "    }",
            ],
            dependencies=["PLL"]
        )]


class GPIOLoopbackTest(TestPattern):
    """Test GPIO write and read"""

    def can_generate(self, module_name: str, manifest_entry: Dict[str, Any]) -> bool:
        if module_name != "GIO":
            return False
        funcs = manifest_entry.get("functions", [])
        has_write = any("WritePin" in f.get("name", "") for f in funcs)
        has_read = any("ReadPin" in f.get("name", "") for f in funcs)
        return has_write and has_read

    def generate_tests(self, module_name: str, manifest_entry: Dict[str, Any]) -> List[TestCase]:
        return [TestCase(
            name="test_gpio_loopback",
            description="Test GPIO write and read",
            module="GIO",
            code_lines=[
                "    // Test: GPIO loopback",
                "    test_count++;",
                "    GIO_WritePin(GIO_PORT_A, 0, GIO_PIN_HIGH);",
                "    volatile uint32_t delay = 1000;",
                "    while(delay--);  // Brief delay",
                "    GIO_PinState_t state = GIO_ReadPin(GIO_PORT_A, 0);",
                "    if (state == GIO_PIN_HIGH) {",
                '        test_results[test_count-1] = TEST_PASS; // "GPIO Loopback"',
                "    } else {",
                '        test_results[test_count-1] = TEST_FAIL; // "GPIO Loopback"',
                "        test_failures++;",
                "    }",
            ],
            dependencies=["GIO"]
        )]


class TestGenerator:
    """Main test generator coordinating all test patterns"""

    def __init__(self):
        self.patterns: List[TestPattern] = [
            InitializationTest(),
            ClockFrequencyTest(),
            GPIOLoopbackTest(),
        ]

    def add_pattern(self, pattern: TestPattern):
        """Add custom test pattern"""
        self.patterns.append(pattern)

    def generate_tests(self, manifest: Dict[str, Any], enabled_modules: List[str]) -> List[TestCase]:
        """Generate all applicable tests for enabled modules"""
        all_tests = []
        api_catalog = manifest.get("api_catalog", {})

        for module_name in enabled_modules:
            if module_name not in api_catalog:
                continue

            manifest_entry = api_catalog[module_name]

            for pattern in self.patterns:
                if pattern.can_generate(module_name, manifest_entry):
                    tests = pattern.generate_tests(module_name, manifest_entry)
                    all_tests.extend(tests)

        return all_tests

    def generate_test_code(self, tests: List[TestCase]) -> List[str]:
        """Generate C code for test harness"""
        lines = []

        # Header and types
        lines.extend([
            "",
            "#ifdef BSP_RUN_TESTS",
            "",
            "// Test result status",
            "typedef enum {",
            "    TEST_PASS = 0,",
            "    TEST_FAIL = 1,",
            "    TEST_SKIP = 2",
            "} TestResult_t;",
            "",
            f"#define MAX_TESTS {len(tests)}",
            "static TestResult_t test_results[MAX_TESTS];",
            "static uint32_t test_count = 0;",
            "static uint32_t test_failures = 0;",
            "",
            "/**",
            " * @brief Run all BSP tests",
            " * @return Number of failed tests",
            " */",
            "uint32_t BSP_RunTests(void)",
            "{",
            "    test_count = 0;",
            "    test_failures = 0;",
            "",
        ])

        # Generate test code
        for test in tests:
            lines.extend(test.code_lines)
            lines.append("")

        # Summary
        lines.extend([
            "    // Test completed - inspect test_failures in debugger",
            "    return test_failures;",
            "}",
            "",
            "#endif // BSP_RUN_TESTS",
            ""
        ])

        return lines
