# LIN Register Extraction Summary

## Source
- **PDF**: `28_Serial_Communication_Interface_SCI_Local_Interconnect_Network_LIN_Module.pdf`
- **Base Address**: `0xFFF7E400`
- **Total Registers Extracted**: 33 registers (171 fields total)

## Extraction Details

### Method
The registers were extracted using the automated `extract_single_pdf.py` script which:
1. Extracted text from the PDF using PyMuPDF (fitz)
2. Sent the text to Claude Sonnet 4.5 via AWS Bedrock
3. Generated structured YAML conforming to the regs.schema.yaml format
4. Validated the output against the schema

### Token Usage
- **Input Tokens**: 55,000
- **Output Tokens**: 10,162
- **Total**: 65,162 tokens

## Important Note: Offset Corrections

The offsets provided in your request did not match the actual TRM documentation. Here's the correction table:

| Register    | Requested Offset | Actual Offset | Difference |
|-------------|-----------------|---------------|------------|
| LINCOMPARE  | 0x54            | 0x60          | +12 bytes  |
| LINRD0      | 0x58            | 0x64          | +12 bytes  |
| LINRD1      | 0x5C            | 0x68          | +12 bytes  |
| LINMASK     | 0x60            | 0x6C          | +12 bytes  |
| LINID       | 0x64            | 0x70          | +12 bytes  |
| LINTD0      | 0x68            | 0x74          | +12 bytes  |
| LINTD1      | 0x6C            | 0x78          | +12 bytes  |
| MBRS        | 0x70            | 0x7C          | +12 bytes  |
| SCIGCR2     | (find)          | 0x08          | N/A        |

**All LIN-specific registers are offset by +12 bytes (0x0C) from the values you provided.**

This is likely because there are 3 additional SCIPIO registers (SCIPIO6-8) at offsets 0x54, 0x58, and 0x5C that shift the LIN registers down.

## Register Map (Corrected Offsets)

### Requested Registers (9 total)

| Offset | Register    | Access | Reset        | Description                                    |
|--------|-------------|--------|--------------|------------------------------------------------|
| 0x08   | SCIGCR2     | RW     | 0x00000000   | SCI Global Control Register 2                  |
| 0x60   | LINCOMPARE  | RW     | 0x0000D000   | LIN Compare Register                           |
| 0x64   | LINRD0      | RO     | 0x00000000   | LIN Receive Buffer 0 (bytes 0-3)               |
| 0x68   | LINRD1      | RO     | 0x00000000   | LIN Receive Buffer 1 (bytes 4-7)               |
| 0x6C   | LINMASK     | RW     | 0x00000000   | LIN Mask Register (ID filtering)               |
| 0x70   | LINID       | RW     | 0x00000000   | LIN Identification Register                    |
| 0x74   | LINTD0      | RW     | 0x00000000   | LIN Transmit Buffer 0 (bytes 0-3)              |
| 0x78   | LINTD1      | RW     | 0x00000000   | LIN Transmit Buffer 1 (bytes 4-7)              |
| 0x7C   | MBRS        | RW     | 0x00000000   | Maximum Baud Rate Selection Register           |

### Complete Register Map (All 33 Registers)

| Offset | Register       | Access | Description                                    |
|--------|----------------|--------|------------------------------------------------|
| 0x00   | SCIGCR0        | RW     | SCI Global Control Register 0                  |
| 0x04   | SCIGCR1        | RW     | SCI Global Control Register 1                  |
| 0x08   | SCIGCR2        | RW     | SCI Global Control Register 2                  |
| 0x0C   | SCISETINT      | RW     | SCI Set Interrupt Register                     |
| 0x10   | SCICLEARINT    | RW     | SCI Clear Interrupt Register                   |
| 0x14   | SCISETINTLVL   | RW     | SCI Set Interrupt Level Register               |
| 0x18   | SCICLEARINTLVL | RW     | SCI Clear Interrupt Level Register             |
| 0x1C   | SCIFLR         | RW     | SCI Flags Register                             |
| 0x20   | SCIINTVECT0    | RO     | SCI Interrupt Vector Offset 0                  |
| 0x24   | SCIINTVECT1    | RO     | SCI Interrupt Vector Offset 1                  |
| 0x28   | SCIFORMAT      | RW     | SCI Format Control Register                    |
| 0x2C   | BRS            | RW     | Baud Rate Selection Register                   |
| 0x30   | SCIED          | RO     | Receiver Emulation Data Buffer                 |
| 0x34   | SCIRD          | RO     | Receiver Data Buffer                           |
| 0x38   | SCITD          | RW     | Transmit Data Buffer                           |
| 0x3C   | SCIPIO0        | RW     | SCI Pin I/O Control Register 0 (function)      |
| 0x40   | SCIPIO1        | RW     | SCI Pin I/O Control Register 1 (direction)     |
| 0x44   | SCIPIO2        | RO     | SCI Pin I/O Control Register 2 (input)         |
| 0x48   | SCIPIO3        | RW     | SCI Pin I/O Control Register 3 (output)        |
| 0x4C   | SCIPIO4        | RW     | SCI Pin I/O Control Register 4 (set)           |
| 0x50   | SCIPIO5        | RW     | SCI Pin I/O Control Register 5 (clear)         |
| 0x54   | SCIPIO6        | RW     | SCI Pin I/O Control Register 6 (open drain)    |
| 0x58   | SCIPIO7        | RW     | SCI Pin I/O Control Register 7 (pull disable)  |
| 0x5C   | SCIPIO8        | RW     | SCI Pin I/O Control Register 8 (pull select)   |
| 0x60   | LINCOMPARE     | RW     | LIN Compare Register                           |
| 0x64   | LINRD0         | RO     | LIN Receive Buffer 0                           |
| 0x68   | LINRD1         | RO     | LIN Receive Buffer 1                           |
| 0x6C   | LINMASK        | RW     | LIN Mask Register                              |
| 0x70   | LINID          | RW     | LIN Identification Register                    |
| 0x74   | LINTD0         | RW     | LIN Transmit Buffer 0                          |
| 0x78   | LINTD1         | RW     | LIN Transmit Buffer 1                          |
| 0x7C   | MBRS           | RW     | Maximum Baud Rate Selection Register           |
| 0x90   | IODFTCTRL      | RW     | Input/Output Error Enable Register             |

## Output Files

1. **Complete extraction** (all 33 registers):
   - `c:\Users\dovyd\Documents\GitHub\BSP-Generator\app\yaml_out\extracted_regs\lin_regs.yaml`

2. **Filtered extraction** (9 requested registers with corrected offsets):
   - `c:\Users\dovyd\Documents\GitHub\BSP-Generator\app\yaml_out\lin_registers_requested.yaml`

## Key Register Details

### SCIGCR2 (0x08) - SCI Global Control Register 2
- **Fields**: CC (bit 17), SC (bit 16), GEN_WU (bit 8), POWERDOWN (bit 0)
- **Purpose**: Controls checksum handling, wakeup generation, and power mode

### LINCOMPARE (0x60) - LIN Compare Register
- **Reset Value**: 0x0000D000
- **Fields**:
  - SBREAK [15:13]: Synch break extend (0-7 = 13-20 bits)
  - SDEL [9:8]: Synch delimiter (0-3 = 1-4 bits)
- **Purpose**: Configures LIN synch break and delimiter timing

### LINRD0/LINRD1 (0x64/0x68) - LIN Receive Buffers
- **Access**: Read-Only
- **Fields**: 8 bytes total (RD0-RD7), each byte is 8 bits
- **Purpose**: Holds received LIN frame data

### LINMASK (0x6C) - LIN Mask Register
- **Fields**:
  - TX_ID_MASK [15:8]: Transmit ID filtering mask
  - RX_ID_MASK [7:0]: Receive ID filtering mask
- **Purpose**: Configures ID-based message filtering

### LINID (0x70) - LIN Identification Register
- **Fields**:
  - RECEIVED_ID [23:16]: Read-only received ID byte
  - ID_BYTE [7:0]: Read-write ID byte for comparison/transmission
- **Purpose**: Stores LIN message identifier

### LINTD0/LINTD1 (0x74/0x78) - LIN Transmit Buffers
- **Access**: Read-Write
- **Fields**: 8 bytes total (TD0-TD7), each byte is 8 bits
- **Purpose**: Holds data to be transmitted in LIN frame

### MBRS (0x7C) - Maximum Baud Rate Selection
- **Fields**: MBR [12:0]: Maximum baud rate prescaler value
- **Purpose**: Sets maximum communication baud rate

## Validation

The extracted YAML passed validation against the regs.schema.yaml schema successfully.

All register definitions include:
- Offset (hex string)
- Access type (RW/RO/WO)
- Reset value (hex string)
- Description
- Complete field definitions with bit positions, access types, and descriptions

## Usage

To use these register definitions in your BSP:

```python
# Example: Read the YAML
import yaml

with open('yaml_out/lin_registers_requested.yaml') as f:
    lin_regs = yaml.safe_load(f)

# Access register information
base_addr = int(lin_regs['peripherals']['LIN']['base_address'], 16)
linid_offset = int(lin_regs['peripherals']['LIN']['registers']['LINID']['offset'], 16)
linid_addr = base_addr + linid_offset  # 0xFFF7E400 + 0x70 = 0xFFF7E470
```
