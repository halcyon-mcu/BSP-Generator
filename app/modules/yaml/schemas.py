"""
Pydantic models for YAML schema validation.

These models validate the structure and types of YAML configuration files
used by the BSP Generator.
"""

from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
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
    freq_hz: Optional[int] = Field(None, gt=0, description="Frequency in Hz")
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

class MuxInfo(BaseModel):
    """Multiplexer configuration for a pin function."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    register_name: str = Field(..., description="Mux control register name", alias='register')
    bit: int = Field(..., ge=0, description="Bit position in register")


class PinFunction(BaseModel):
    """Pin function/alternate function definition."""
    model_config = ConfigDict(extra='allow')

    af: str = Field(..., description="Alternate function number")
    signal: str = Field(..., description="Signal name for this function")
    mux: MuxInfo = Field(..., description="Mux register configuration")


class BoardInfo(BaseModel):
    """Board-specific pin information."""
    model_config = ConfigDict(extra='allow')

    net: Optional[str] = Field(None, description="Net name on board")


class PinDefinition(BaseModel):
    """Pin definition in pinmux.yaml."""
    model_config = ConfigDict(extra='allow')

    package_pin: int = Field(..., ge=0, description="Physical package pin number")
    name: str = Field(..., description="Pin name/primary signal")
    board: Optional[BoardInfo] = Field(None, description="Board-specific info")
    functions: List[PinFunction] = Field(..., description="Available alternate functions")

    @field_validator('functions')
    @classmethod
    def validate_functions_not_empty(cls, v: List) -> List:
        """Ensure functions list is not empty."""
        if not v:
            raise ValueError("functions list cannot be empty")
        return v


class PinmuxYAML(BaseModel):
    """Root schema for pinmux.yaml."""
    model_config = ConfigDict(extra='allow')

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
# BOARD.YAML SCHEMA
# ==============================================================================

class BoardIdentity(BaseModel):
    """Board identity metadata."""
    model_config = ConfigDict(extra='allow')

    name: str
    revision: str

    @field_validator('name', 'revision')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class BoardMcu(BaseModel):
    """Board MCU package identity."""
    model_config = ConfigDict(extra='allow')

    part_number: str
    package: str

    @field_validator('part_number', 'package')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class BoardPreferredDebugPath(BaseModel):
    """Canonical preferred terminal/UART route used for bring-up."""
    model_config = ConfigDict(extra='allow')

    peripheral: Literal["LIN", "SCI", "UART"]
    mode: Literal["SCI", "UART"]
    instance: str
    rx_pin: int = Field(..., ge=0)
    tx_pin: int = Field(..., ge=0)
    af: int = Field(..., ge=0)

    @field_validator('peripheral', 'mode', mode='before')
    @classmethod
    def normalize_upper_token(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip().upper()

    @field_validator('instance')
    @classmethod
    def validate_instance(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class BoardCommunication(BaseModel):
    """Board communication routing."""
    model_config = ConfigDict(extra='allow')

    preferred_debug_path: BoardPreferredDebugPath


class BoardLed(BaseModel):
    """LED mapping required for generated board capability header."""
    model_config = ConfigDict(extra='allow')

    designator: str
    function: str
    mcu_pin: int = Field(..., ge=0)
    active_state: Literal["LOW", "HIGH"]
    gpio: Optional[str] = None

    @field_validator('designator', 'function')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('active_state', mode='before')
    @classmethod
    def normalize_active_state(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip().upper()

    @field_validator('gpio')
    @classmethod
    def validate_gpio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        token = v.strip()
        if not token:
            return None
        if not re.match(r"^GIO[A-Za-z]\[\d+\]$", token):
            raise ValueError("gpio must match GIO<port>[<pin>] when provided")
        return token


class BoardButton(BaseModel):
    """Button mapping required for generated board capability header."""
    model_config = ConfigDict(extra='allow')

    designator: str
    function: str
    mcu_pin: int = Field(..., ge=0)
    active_state: Literal["LOW", "HIGH"]
    gpio: Optional[str] = None

    @field_validator('designator', 'function')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('active_state', mode='before')
    @classmethod
    def normalize_active_state(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip().upper()

    @field_validator('gpio')
    @classmethod
    def validate_gpio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        token = v.strip()
        if not token:
            return None
        if not re.match(r"^GIO[A-Za-z]\[\d+\]$", token):
            raise ValueError("gpio must match GIO<port>[<pin>] when provided")
        return token


class BoardYAML(BaseModel):
    """Root schema for board.yaml used by board capability header generation."""
    model_config = ConfigDict(extra='allow')

    ir_schema_version: str
    board: BoardIdentity
    mcu: BoardMcu
    communication: BoardCommunication
    leds: List[BoardLed] = Field(..., min_length=1)
    buttons: List[BoardButton] = Field(..., min_length=1)


# ==============================================================================
# BRINGUP CONTRACT YAML SCHEMA (Optional)
# ==============================================================================

class BringupRequiredPin(BaseModel):
    """Required pin mux selection for deterministic bring-up."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    pin: int = Field(..., ge=0)
    register_name: str = Field(..., alias='register')
    bit: int = Field(..., ge=0)
    af: int = Field(..., ge=0)


class BringupSerialContract(BaseModel):
    """Serial-path requirements for bring-up."""
    model_config = ConfigDict(extra='allow')

    primary_path: str
    primary_tx_only: Optional[Literal["LIN", "SCI", "BOTH"]] = None
    baud_default: int = Field(..., gt=0)
    required_pins: List[BringupRequiredPin] = Field(default_factory=list)


class BringupLinRegisterRule(BaseModel):
    """Required LIN register value."""
    model_config = ConfigDict(extra='allow')

    required_value: str


class BringupLinRegisters(BaseModel):
    """LIN register constraints."""
    model_config = ConfigDict(extra='allow')

    SCIPIO0: Optional[BringupLinRegisterRule] = None


class BringupLinContract(BaseModel):
    """LIN bring-up constraints."""
    model_config = ConfigDict(extra='allow')

    required_registers: BringupLinRegisters


class BringupIommContract(BaseModel):
    """IOMM bring-up constraints."""
    model_config = ConfigDict(extra='allow')

    unlock_sequence: List[str] = Field(default_factory=list)
    require_unlock_for_pin_config: bool = True
    require_lock_after_pin_config: bool = True
    configurepin_self_managed_locking: bool = True


class BringupPllContract(BaseModel):
    """PLL bring-up constraints."""
    model_config = ConfigDict(extra='allow')

    init_profile: Optional[str] = None
    required_sequence: List[str] = Field(default_factory=list)

    class FrequencyDecodeRule(BaseModel):
        model_config = ConfigDict(extra='allow')

        class RequiredBehaviorRule(BaseModel):
            model_config = ConfigDict(extra='allow')

            supports_hal_encoded_pllmul_literal: bool = False
            uses_hal_literal_hclk_override: bool = False
            uses_uint64_intermediate_math: bool = False
            derives_active_source_from_ghvsrc: bool = False
            uses_trm_field_decoding: bool = False
            uses_trm_enable_disable_sequence: bool = False

        allow_hal_encoded_pllmul: bool = False
        hal_literal_hclk_hz: Optional[int] = Field(default=None, gt=0)
        required_behavior: Optional[RequiredBehaviorRule] = None
        required_tokens: List[str] = Field(default_factory=list)

    frequency_decode: Optional[FrequencyDecodeRule] = None


class BringupFlashRegisterRule(BaseModel):
    """Flash wait-state register constraints."""
    model_config = ConfigDict(extra='allow')

    address: str
    required_value: Optional[str] = None
    required_write_tokens: List[str] = Field(default_factory=list)


class BringupFlashContract(BaseModel):
    """Flash bring-up constraints."""
    model_config = ConfigDict(extra='allow')

    required_registers: Dict[str, BringupFlashRegisterRule] = Field(default_factory=dict)


class BringupStartupContract(BaseModel):
    """Startup ordering constraints."""
    model_config = ConfigDict(extra='allow')

    required_order: List[str] = Field(default_factory=list)


class BringupContractYAML(BaseModel):
    """Root schema for bringup_contract.yaml (optional)."""
    model_config = ConfigDict(extra='allow')

    serial: BringupSerialContract
    lin: Optional[BringupLinContract] = None
    iomm: Optional[BringupIommContract] = None
    pll: Optional[BringupPllContract] = None
    flash: Optional[BringupFlashContract] = None
    startup: Optional[BringupStartupContract] = None


# ==============================================================================
# GENERATION PROFILE YAML SCHEMA (Optional)
# ==============================================================================

class BspValidationFrameConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    data_bits: int = Field(..., ge=5, le=9)
    stop_bits: int = Field(..., ge=1, le=2)
    parity: Literal["none", "even", "odd"]


class BspValidationBannerConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    sci: str
    lin: str


class BspValidationTimingConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    heartbeat_ticks: int = Field(..., ge=1)
    tx_period_ticks: int = Field(..., ge=1)
    busy_delay: int = Field(..., ge=0)


class BspValidationProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    enabled: Optional[bool] = None
    baud: Optional[int] = Field(default=None, gt=0)
    primary_serial_path: Optional[Literal["lin_only", "sci_only", "dual"]] = None
    frame: Optional[BspValidationFrameConfig] = None
    banners: Optional[BspValidationBannerConfig] = None
    timing: Optional[BspValidationTimingConfig] = None


class BuildGateProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    class LlmRewriteProfile(BaseModel):
        model_config = ConfigDict(extra='allow')

        enabled: Optional[bool] = None
        scope: Optional[Literal["top_files"]] = None
        top_k_files: Optional[int] = Field(default=None, ge=1)
        apply_policy: Optional[Literal["hybrid", "diff_only", "full_file_only"]] = None
        model: Optional[Literal["inherit", "haiku4.5", "sonnet4.5", "opus4.5", "opus4.6"]] = None
        max_tokens: Optional[int] = Field(default=None, ge=256)
        max_attempts: Optional[int] = Field(default=None, ge=0)
        include_contract_context: Optional[bool] = None

    enabled: Optional[bool] = None
    mode: Optional[Literal["strict", "advisory", "off"]] = None
    external_workspace_path: Optional[str] = None
    project_name: Optional[str] = None
    configuration: Optional[Literal["Debug", "Release"]] = None
    max_fix_rounds: Optional[int] = Field(default=None, ge=0)
    allow_targeted_llm_rewrite: Optional[bool] = None
    fail_on_compile_error: Optional[bool] = None
    clean_stale_project_files: Optional[bool] = None
    clean_build: Optional[bool] = None
    llm_rewrite: Optional[LlmRewriteProfile] = None


class BringupModeProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    default: Optional[Literal["direct_init", "validation"]] = None


class StartupContractProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    gate_mode: Optional[Literal["warn", "fail"]] = None


class ParityGuardProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    mode: Optional[Literal["critical_only", "strict", "off"]] = None
    baseline_path: Optional[str] = None
    critical_registers: Optional[List[str]] = None


class AppIntentProfile(BaseModel):
    model_config = ConfigDict(extra='allow')

    enabled: Optional[bool] = None
    critical_file_freeze: Optional[bool] = None
    allow_llm_on_critical: Optional[bool] = None
    task_library_path: Optional[str] = None
    intent_refs_mode: Optional[Literal["proven_only", "include_unverified"]] = None
    generate_firmware_pass: Optional[bool] = None
    post_gen_max_tokens: Optional[int] = Field(default=None, ge=1024)


class GenerationProfileYAML(BaseModel):
    """Schema for generation_profile.yaml."""
    model_config = ConfigDict(extra='allow')

    target_board: Optional[str] = None
    modules: Optional[Dict[str, Any]] = None
    sci: Optional[Dict[str, Any]] = None
    pins: Optional[Dict[str, Any]] = None
    clocks: Optional[Dict[str, Any]] = None
    strict_validation: Optional[bool] = None
    contract_mode: Optional[Literal["auto_fix_then_fail", "hard_fail", "warn_only"]] = None
    require_ccs_proof: Optional[bool] = None
    bringup: Optional[Dict[str, Any]] = None
    build_gate: Optional[BuildGateProfile] = None
    bsp_validation: Optional[BspValidationProfile] = None
    bringup_mode: Optional[BringupModeProfile] = None
    startup_contract: Optional[StartupContractProfile] = None
    parity_guard: Optional[ParityGuardProfile] = None
    app_intent: Optional[AppIntentProfile] = None


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
