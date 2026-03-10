---
marp: true
theme: default
class: invert
paginate: true
html: true
style: |
  section {
    background-color: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', sans-serif;
  }
  h1 { color: #93c5fd; font-size: 2em; }
  h2 { color: #7dd3fc; border-bottom: 2px solid #334155; padding-bottom: 0.3em; }
  strong { color: #fbbf24; }
  table { width: 100%; }
  th { background: #1e3a5f; color: #93c5fd; }
  td { border-color: #334155; }
  code { background: #1e293b; color: #86efac; }
  blockquote { border-left: 4px solid #3b82f6; color: #94a3b8; }
  .mermaid { display: flex; justify-content: center; }
  .mermaid svg { max-height: 380px; max-width: 100%; }
---

<!--
# How to Use This File

## Rendering Mermaid Diagrams (IMPORTANT)

Marp does not render Mermaid natively. This file uses Mermaid.js via HTML mode.

### Step 1 — Enable HTML in VS Code Marp settings
Add to VS Code settings.json (Ctrl+Shift+P → "Open User Settings JSON"):
  "markdown.marp.enableHtml": true

### Step 2 — Preview
1. Install the "Marp for VS Code" extension (marp-team.marp-vscode)
2. Open SLIDES.md
3. Click the Marp preview icon (top-right of editor tab bar)

### Step 3 — Export
- HTML (recommended for presenting): Command Palette → "Marp: Export Slide Deck" → HTML
  Open the exported .html in a browser — all diagrams render fully.
- PDF: Diagrams render during PDF export only if Chromium/Puppeteer is available.
  If diagrams appear blank in PDF, export to HTML and print to PDF from the browser.

### Option B — Individual Mermaid Diagrams (for PowerPoint / Google Slides)
1. Copy any diagram source from between the <div class="mermaid"> tags
2. Paste at https://mermaid.live
3. Export as PNG/SVG → paste into your slide tool
-->

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true, theme: 'dark', securityLevel: 'loose' });</script>

# AI-Driven BSP Generator

## From Hardware Description to Compiled Firmware

---

**Target Hardware:** LAUNCHXL2-TMS57012-RM46 · TI Hercules RM46 · Cortex-R4F @ 220 MHz

**Toolchain:** Python · Claude AI (AWS Bedrock) · TI Code Composer Studio

---

## The Big Picture

> Describe hardware in YAML once — get a complete, compiled BSP and application firmware.

<div class="mermaid">
flowchart LR
    A[/"9 YAML
    Hardware Files"/] --> B["Claude AI
    AWS Bedrock"]
    B --> C["Validated C BSP
    28+ source files"]
    C --> D[/"User types:
    'blink LED on button'"/]
    D --> E["Claude AI
    AWS Bedrock"]
    E --> F["Compiled
    Firmware Binary"]
    style A fill:#1e40af,color:#fff
    style B fill:#6d28d9,color:#fff
    style C fill:#065f46,color:#fff
    style D fill:#92400e,color:#fff
    style E fill:#6d28d9,color:#fff
    style F fill:#065f46,color:#fff
</div>

---

## YAML Input Ecosystem

> Every register address, clock divider, and pin assignment comes from YAML — the LLM **never invents values**.

<div class="mermaid">
graph LR
    subgraph hw["Hardware Description"]
        SOC["soc.yaml · 70 KB
        20+ peripherals"]
        REGS["regs.yaml · 407 KB
        All register definitions"]
        IRQ["irq.yaml
        interrupt vectors"]
        MEM["memmap.yaml
        Flash & RAM"]
    end
    subgraph clk["Clock System"]
        BUS["bus.yaml
        PLL config · clock domains"]
    end
    subgraph phy["Physical Layer"]
        PIN["pinmux.yaml
        144-pin IOMM mux"]
        BOARD["board.yaml
        LEDs · buttons"]
    end
    subgraph saf["Safety & Config"]
        CONTRACT["bringup_contract.yaml
        Hardware safety constraints"]
        PROFILE["generation_profile.yaml
        Generation settings"]
    end
    SOC -->|regs_ref| REGS
    SOC -->|clock_ref| BUS
    SOC -->|irq_ref| IRQ
</div>

---

## 3-Pass Generation Pipeline

> Three sequential LLM passes, each building on the last.

<div class="mermaid">
flowchart LR
    Y[/"YAML
    9 files"/] --> P1["Pass 1 — Discovery
    reg_*.h  register typedefs
    bsp_manifest.json  API catalog"]
    P1 --> P2["Pass 2 — Implementation
    *_driver.h  driver headers
    *_driver.c  driver sources
    15 concurrent · 3 retries each"]
    P2 --> P3["Pass 3 — Platform Files
    system.c · entry.c · start.s
    vim.c · linker.cmd · main.c
    generated in parallel"]
    P3 --> OUT[/"Compilable BSP
    ~28 source files"/]
    style Y fill:#1e40af,color:#fff
    style P1 fill:#6d28d9,color:#fff
    style P2 fill:#6d28d9,color:#fff
    style P3 fill:#6d28d9,color:#fff
    style OUT fill:#065f46,color:#fff
</div>

---

## FACTS Protocol: No Hallucinations

> Every hex constant the LLM writes must be declared and sourced from YAML first.

<div class="mermaid">
flowchart LR
    YAML["regs.yaml
    PLL_BASE = 0xFFFFFE00
    PLLCTL1_OFFSET = 0x070"]
    YAML -->|"embedded in prompt"| MIRROR["FACTS MIRROR
    declared before
    any code block"]
    MIRROR --> LLM["Claude AI
    generates
    pll_driver.c"]
    LLM --> VAL["Validator
    checks every hex
    vs. YAML origin"]
    VAL -->|"✓ traced"| PASS["ACCEPT"]
    VAL -->|"✗ invented"| FAIL["REJECT → retry"]
    style YAML fill:#1e40af,color:#fff
    style MIRROR fill:#1e3a5f,color:#fff
    style LLM fill:#6d28d9,color:#fff
    style VAL fill:#1e3a5f,color:#fff
    style PASS fill:#059669,color:#fff
    style FAIL fill:#dc2626,color:#fff
</div>

---

## 8-Stage Validation Pipeline

> Every stage either warns, retries, or aborts — nothing slips through.

<div class="mermaid">
flowchart LR
    subgraph PRE["Pre-Generation"]
        S0["0 · YAML Schema
        abort before any API call"]
    end
    subgraph GEN["Generation Passes"]
        S1["1 · Pass 1 Headers
        invented addresses → abort"]
        S2["2 · FACTS MIRROR
        untraceable constants → fail"]
        S3["3 · Pass 2 Drivers
        API drift · PLL order → retry ×3"]
        S4["4 · Module Contract
        signature drift → autofix"]
    end
    subgraph POST["Post-Generation"]
        S5["5 · Startup Contract
        wrong init order → fail"]
        S6["6 · Parity Guard
        register drift → diff report"]
        S7["7 · CCS Build Gate
        compiler errors → LLM rewrite ×4"]
    end
    PRE --> GEN --> POST
    style S0 fill:#7f1d1d,color:#fff
    style S1 fill:#7f1d1d,color:#fff
    style S2 fill:#1e3a5f,color:#fff
    style S3 fill:#1e3a5f,color:#fff
    style S4 fill:#1e3a5f,color:#fff
    style S5 fill:#7f1d1d,color:#fff
    style S6 fill:#1e3a5f,color:#fff
    style S7 fill:#7f1d1d,color:#fff
</div>

---

## Critical Hardware Safety Constraint

> CLKCNTL (VCLKR divider) **must** be written **before** switching the clock source.

<div class="mermaid">
flowchart LR
    subgraph WRONG["❌ Wrong order — Hardware Fault"]
        direction TB
        W1["GHVSRC → PLL1
        HCLK = 220 MHz"]
        W2["CLKCNTL not yet written
        VCLKR = 0  (divide-by-1)"]
        W3["VCLK = 220 MHz
        exceeds 110 MHz limit"]
        W1 --> W2 --> W3
    end
    subgraph CORRECT["✓ Correct order"]
        direction TB
        R1["CLKCNTL: VCLKR = 1
        divider = 2"]
        R2["GHVSRC → PLL1
        HCLK = 220 MHz"]
        R3["VCLK = 110 MHz
        within limit"]
        R1 --> R2 --> R3
    end
    style W3 fill:#dc2626,color:#fff
    style R3 fill:#059669,color:#fff
</div>

Enforced by `pass2_validator.py`, `startup_contract_validator.py`, and `ti_diagnostics.py`

---

## Auto-Mitigation: 3-Tier Escalation

> The system heals itself before giving up.

<div class="mermaid">
flowchart LR
    F["Validation
    Failure"] --> T1["Tier 1 · Deterministic Fixes
    16 regex-based text transforms
    No LLM — instant"]
    T1 -->|"fixed"| OK["✓ Continue"]
    T1 -->|"still failing"| T2["Tier 2 · Contract Autofix
    Behavioral corrections
    IOMM encoding · LIN wrappers"]
    T2 -->|"fixed"| OK
    T2 -->|"still failing"| T3["Tier 3 · LLM Targeted Rewrite
    Compiler errors → unified diff
    Top 2 error files · max 4 rounds"]
    T3 -->|"fixed"| OK
    T3 -->|"exhausted"| FAIL["Report & Fail"]
    style F fill:#92400e,color:#fff
    style T1 fill:#1e3a5f,color:#fff
    style T2 fill:#1e3a5f,color:#fff
    style T3 fill:#6d28d9,color:#fff
    style OK fill:#059669,color:#fff
    style FAIL fill:#dc2626,color:#fff
</div>

---

## Capstone: Firmware from a Sentence

> The full end-to-end journey — one natural language sentence to a compiled binary.

<div class="mermaid">
flowchart LR
    Y[/"9 YAML
    Files"/] --> BSP["3-Pass
    BSP Generation"]
    BSP --> CAP["Board Capability
    Manifest
    LED2 · S3 · SCI_TERMINAL"]
    CAP --> USR[/"User types:
    'blink LED2 when
    S3 is pressed'"/]
    USR --> VLD["Validate
    components
    exist in BSP"]
    VLD --> FW["Firmware Generation
    LLM + BSP headers
    as context"]
    FW --> CCS["CCS
    Compile Gate"]
    CCS --> BIN["Compiled Binary
    ready to flash"]
    style Y fill:#1e40af,color:#fff
    style BSP fill:#6d28d9,color:#fff
    style CAP fill:#065f46,color:#fff
    style USR fill:#7c3aed,color:#fff
    style VLD fill:#1e3a5f,color:#fff
    style FW fill:#6d28d9,color:#fff
    style CCS fill:#1e3a5f,color:#fff
    style BIN fill:#059669,color:#fff
</div>

---

## By The Numbers

| | |
|---|---|
| **9** YAML input files | **28+** generated source files |
| **3** LLM generation passes | **15** concurrent modules (Pass 2) |
| **8** validation stages | **16** deterministic auto-fixes |
| **11** hardware constraints | **4** LLM rewrite rounds (max) |
| **1 sentence** | → compiled firmware |

---

> *From `python main.py` to a flashable `.out` — no manual register lookups, no hand-written HAL.*
