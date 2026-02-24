"""
Pydantic models for YAML schema validation.

These models validate the structure and types of YAML configuration files
used by the BSP Generator.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ==============================================================================
# REGS.YAML SCHEMA
# ==============================================================================

class Register(BaseModel):
    """Individual register definition."""
    offset: str = Field(..., description="Register offset (hex string)")
    access: str = Field(..., description="Access type: RW, RO, WO, RC, W1C")
    reset: str = Field(..., description="Reset value (hex string)")
    desc: str = Field(..., description="Register description")

    @field_validator('offset', 'reset')
    @classmethod
    def validate_hex_string(cls, v: str) -> str:
        """Validate that value is a hex string starting with 0x."""
        if not isinstance(v, str):
            raise ValueError(f"Must be string, got {type(v)}")
        if not v.startswith('0x'):
            raise ValueError(f"Must be hex string starting with 0x, got: {v}")
        # Validate it's valid hex
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hex string: {v}")
        return v

    @field_validator('access')
    @classmethod
    def validate_access_type(cls, v: str) -> str:
        """Validate access type is one of the allowed values."""
        valid_access = {'RW', 'RO', 'WO', 'RC', 'W1C', 'WC', 'RW1C'}
        if v not in valid_access:
            raise ValueError(f"Access type must be one of {valid_access}, got: {v}")
        return v


class PeripheralRegs(BaseModel):
    """Peripheral register block definition."""
    base_address: str = Field(..., description="Base address (hex string)")
    desc: str = Field(..., description="Peripheral description")
    registers: Dict[str, Register] = Field(..., description="Register definitions")

    @field_validator('base_address')
    @classmethod
    def validate_hex_address(cls, v: str) -> str:
        """Validate base address is valid hex."""
        if not v.startswith('0x'):
            raise ValueError(f"Base address must start with 0x, got: {v}")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hex address: {v}")
        return v


class RegsYAML(BaseModel):
    """Root schema for regs.yaml."""
    peripherals: Dict[str, PeripheralRegs] = Field(..., description="Peripheral register blocks")

    @field_validator('peripherals')
    @classmethod
    def validate_not_empty(cls, v: Dict) -> Dict:
        """Ensure peripherals dict is not empty."""
        if not v:
            raise ValueError("peripherals cannot be empty")
        return v


# ==============================================================================
# SOC.YAML SCHEMA
# ==============================================================================

class PeripheralSoc(BaseModel):
    """Peripheral definition in soc.yaml."""
    model_config = {"extra": "allow"}  # Allow extra fields like x-ext, base_address

    name: str = Field(..., description="Peripheral name")
    regs_ref: str = Field(..., description="Reference to register block in regs.yaml")
    clock_ref: Optional[str] = Field(None, description="Clock domain reference")
    irq_ref: Optional[List[str]] = Field(None, description="IRQ references")
    type: Optional[str] = Field(None, description="Peripheral type")

    @field_validator('name', 'regs_ref')
    @classmethod
    def validate_not_empty_string(cls, v: str) -> str:
        """Validate required strings are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v


class SocSection(BaseModel):
    """The 'soc' section within soc.yaml."""
    model_config = {"extra": "allow"}  # Allow extra fields like cpu

    peripherals: List[PeripheralSoc] = Field(..., description="Peripheral definitions")

    @field_validator('peripherals')
    @classmethod
    def validate_peripherals_not_empty(cls, v: List) -> List:
        """Ensure peripherals list is not empty."""
        if not v:
            raise ValueError("peripherals list cannot be empty")
        return v

    @field_validator('peripherals')
    @classmethod
    def validate_unique_names(cls, v: List[PeripheralSoc]) -> List[PeripheralSoc]:
        """Ensure peripheral names are unique."""
        names = [p.name for p in v]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            raise ValueError(f"Duplicate peripheral names: {set(duplicates)}")
        return v


class SocYAML(BaseModel):
    """Root schema for soc.yaml."""
    model_config = {"extra": "allow"}  # Allow extra fields like ir_schema_version, vendor, etc.

    chip: str = Field(..., description="Chip name")
    family: str = Field(..., description="Chip family")
    soc: SocSection = Field(..., description="SOC section with peripherals")


# ==============================================================================
# BUS.YAML SCHEMA
# ==============================================================================

class ClockSource(BaseModel):
    """Clock source definition."""
    name: str
    freq_hz: int = Field(..., gt=0, description="Frequency in Hz")
    desc: Optional[str] = None


class ClockDomain(BaseModel):
    """Clock domain definition."""
    name: str
    divider: Optional[int] = Field(None, gt=0)
    source: Optional[str] = None
    desc: Optional[str] = None


class BusYAML(BaseModel):
    """Root schema for bus.yaml."""
    sources: List[ClockSource] = Field(..., description="Clock sources")
    domains: List[ClockDomain] = Field(..., description="Clock domains")

    @field_validator('sources', 'domains')
    @classmethod
    def validate_not_empty(cls, v: List) -> List:
        """Ensure lists are not empty."""
        if not v:
            raise ValueError("List cannot be empty")
        return v


# ==============================================================================
# IRQ.YAML SCHEMA
# ==============================================================================

class Interrupt(BaseModel):
    """Interrupt definition."""
    name: str
    number: int = Field(..., ge=0, description="IRQ number")
    desc: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v or not v.strip():
            raise ValueError("Interrupt name cannot be empty")
        return v


class IrqYAML(BaseModel):
    """Root schema for irq.yaml."""
    interrupt_controller: str = Field(..., description="Interrupt controller name")
    irqs: List[Interrupt] = Field(..., description="Interrupt definitions")

    @field_validator('irqs')
    @classmethod
    def validate_not_empty(cls, v: List) -> List:
        """Ensure irqs list is not empty."""
        if not v:
            raise ValueError("irqs list cannot be empty")
        return v

    @field_validator('irqs')
    @classmethod
    def validate_unique_names_and_numbers(cls, v: List[Interrupt]) -> List[Interrupt]:
        """Ensure IRQ names and numbers are unique."""
        names = [irq.name for irq in v]
        numbers = [irq.number for irq in v]

        dup_names = [name for name in names if names.count(name) > 1]
        if dup_names:
            raise ValueError(f"Duplicate IRQ names: {set(dup_names)}")

        dup_nums = [num for num in numbers if numbers.count(num) > 1]
        if dup_nums:
            raise ValueError(f"Duplicate IRQ numbers: {set(dup_nums)}")

        return v


# ==============================================================================
# PINMUX.YAML SCHEMA
# ==============================================================================

class PinDefinition(BaseModel):
    """Pin definition in pinmux.yaml."""
    pin: Union[int, str] = Field(..., description="Pin number or name")
    signals: List[str] = Field(..., description="Available signal functions")

    @field_validator('signals')
    @classmethod
    def validate_signals_not_empty(cls, v: List) -> List:
        """Ensure signals list is not empty."""
        if not v:
            raise ValueError("signals list cannot be empty")
        return v


class PinmuxYAML(BaseModel):
    """Root schema for pinmux.yaml."""
    pins: List[PinDefinition] = Field(..., description="Pin definitions")

    @field_validator('pins')
    @classmethod
    def validate_not_empty(cls, v: List) -> List:
        """Ensure pins list is not empty."""
        if not v:
            raise ValueError("pins list cannot be empty")
        return v


# ==============================================================================
# MEMMAP.YAML SCHEMA
# ==============================================================================

class MemoryRegion(BaseModel):
    """Memory region definition."""
    name: str
    start: str = Field(..., description="Start address (hex)")
    size: str = Field(..., description="Size (hex)")
    type: str = Field(..., description="Memory type: RAM, ROM, FLASH, etc.")

    @field_validator('start', 'size')
    @classmethod
    def validate_hex(cls, v: str) -> str:
        """Validate hex address/size."""
        if not v.startswith('0x'):
            raise ValueError(f"Must start with 0x, got: {v}")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hex value: {v}")
        return v


class MemmapYAML(BaseModel):
    """Root schema for memmap.yaml."""
    regions: List[MemoryRegion] = Field(..., description="Memory regions")

    @field_validator('regions')
    @classmethod
    def validate_not_empty(cls, v: List) -> List:
        """Ensure regions list is not empty."""
        if not v:
            raise ValueError("regions list cannot be empty")
        return v


# ==============================================================================
# BOARD.YAML SCHEMA (Optional - for future use)
# ==============================================================================

class BoardYAML(BaseModel):
    """Root schema for board.yaml (optional)."""
    board_name: Optional[str] = None
    communication: Optional[Dict[str, Any]] = None
    model_config = {"extra": "allow"}  # Allow extra fields


# ==============================================================================
# VALIDATION HELPERS
# ==============================================================================

def validate_yaml_schema(data: Dict[str, Any], schema_class: type[BaseModel]) -> tuple[bool, List[str]]:
    """
    Validate YAML data against a Pydantic schema.

    Args:
        data: Dictionary loaded from YAML
        schema_class: Pydantic model class to validate against

    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        schema_class(**data)
        return (True, [])
    except Exception as e:
        # Extract error messages from Pydantic validation errors
        errors = []
        if hasattr(e, 'errors'):
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error['loc'])
                msg = error['msg']
                errors.append(f"{loc}: {msg}")
        else:
            errors.append(str(e))
        return (False, errors)
