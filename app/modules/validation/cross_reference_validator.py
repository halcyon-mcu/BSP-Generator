"""
Cross-file reference validation for YAML files.

Validates that references between YAML files are valid (e.g., regs_ref in soc.yaml
actually exists in regs.yaml).
"""

import logging
from typing import Dict, List, Any, Set

logger = logging.getLogger(__name__)


def validate_cross_references(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    irq_data: Dict[str, Any],
    bus_data: Dict[str, Any],
    pinmux_data: Dict[str, Any]
) -> List[str]:
    """
    Validate all cross-references between YAML files.

    Args:
        soc_data: Data from soc.yaml
        regs_data: Data from regs.yaml
        irq_data: Data from irq.yaml
        bus_data: Data from bus.yaml
        pinmux_data: Data from pinmux.yaml

    Returns:
        List of error messages (empty if all references are valid)
    """
    errors = []

    # Build available reference sets
    available_regs = set(regs_data.get("peripherals", {}).keys())
    available_irqs = {irq.get("name") for irq in irq_data.get("irqs", []) if irq.get("name")}

    # Build available clock domains from both sources and domains
    available_clocks = set()
    for source in bus_data.get("sources", []):
        if source.get("name"):
            available_clocks.add(source.get("name"))
    for domain in bus_data.get("domains", []):
        if domain.get("name"):
            available_clocks.add(domain.get("name"))

    # Get peripherals list (handle nested structure)
    peripherals = soc_data.get("soc", {}).get("peripherals", [])
    if not peripherals:
        # Fallback for flat structure
        peripherals = soc_data.get("peripherals", [])

    # Validate each peripheral in soc.yaml
    for idx, periph in enumerate(peripherals):
        periph_name = periph.get("name", f"peripheral_{idx}")

        # Validate regs_ref
        regs_ref = periph.get("regs_ref")
        if regs_ref:
            if regs_ref not in available_regs:
                errors.append(
                    f"{periph_name}: regs_ref '{regs_ref}' not found in regs.yaml"
                )
        else:
            # regs_ref is required (caught by schema validation, but good to check)
            errors.append(f"{periph_name}: missing required regs_ref field")

        # Validate clock_ref (optional)
        clock_ref = periph.get("clock_ref")
        if clock_ref and clock_ref not in available_clocks:
            errors.append(
                f"{periph_name}: clock_ref '{clock_ref}' not found in bus.yaml"
            )

        # Validate irq_ref array (optional)
        irq_refs = periph.get("irq_ref", [])
        if isinstance(irq_refs, list):
            for irq_ref in irq_refs:
                if irq_ref and irq_ref not in available_irqs:
                    errors.append(
                        f"{periph_name}: irq_ref '{irq_ref}' not found in irq.yaml"
                    )
        elif irq_refs:  # Single IRQ reference (string)
            if irq_refs not in available_irqs:
                errors.append(
                    f"{periph_name}: irq_ref '{irq_refs}' not found in irq.yaml"
                )

        # TODO: Validate pin references against pinmux.yaml
        # This is more complex as pin references can be in various formats

    return errors


def validate_and_report_cross_references(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    irq_data: Dict[str, Any],
    bus_data: Dict[str, Any],
    pinmux_data: Dict[str, Any]
) -> bool:
    """
    Validate cross-references and log results.

    Returns:
        True if all references are valid, False otherwise
    """
    errors = validate_cross_references(
        soc_data, regs_data, irq_data, bus_data, pinmux_data
    )

    if errors:
        logger.error("Cross-reference validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    else:
        logger.info("Cross-reference validation passed")
        return True
