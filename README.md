# LIDER: LLM-based Incremental Design Engineering and Refinement

A tool framework leveraging Large Language Models to automate ASIC design verification and timing closure tasks using Google's Gemini 2.0 Flash API and OpenSTA.

## Overview

LIDER automates the verification-implementation loop in ASIC design by:
- Analyzing Verilog designs and Liberty cell libraries
- Generating timing constraints (SDC) from natural language descriptions
- Running static timing analysis (STA) using OpenSTA
- Automatically fixing timing violations through iterative refinement
- Maintaining complete documentation and change history

## Prerequisites

### Software Requirements
- Python 3.8+
- OpenSTA (Static Timing Analysis tool)
- Google Gemini API key

### Python Dependencies
```bash
pip install requests
```

## Installation

### 1. Install OpenSTA

**macOS:**
```bash
brew install opensta
```

**Linux:**
```bash
git clone https://github.com/The-OpenROAD-Project/OpenSTA.git
cd OpenSTA
mkdir build && cd build
cmake ..
make
sudo make install
```

**Verify:**
```bash
which sta
sta -version
```

### 2. Get Gemini API Key

1. Visit https://ai.google.dev/gemini-api
2. Sign in and create an API key
3. Save the key securely

### 3. Clone Repository

```bash
git clone https://github.com/your-username/LIDER.git
cd LIDER
```

## Configuration

Edit these paths in the script (lines 10-12):

```python
OPENSTA_PATH = "/usr/local/bin/sta"              # Path to OpenSTA binary
DEFAULT_LIBERTY_PATH = "/path/to/library.lib"    # Default Liberty file path
WORKING_DIRECTORY = "/path/to/workspace"         # Working directory
```

## Usage

### Run the Tool

```bash
python lider.py
```

### Enter API Key

When prompted:
```
ADD YOUR GEMINI API KEY: [paste your key]
```

### Select Mode

```
What help do you want from our tool?
Options:
1) Verilog Design Analysis
2) Liberty File Analysis for Design Cells
3) SDC & TCL Generation
4) Timing Analysis & Violation Fixing (Combined)
5) Run all

Enter your choice (1-5):
```

## Input Files

| Mode | Required Files |
|------|----------------|
| 1 | Verilog netlist (.v) |
| 2 | Verilog netlist (.v), Liberty file (.lib) |
| 3 | Verilog netlist (.v), Liberty file (.lib), Timing requirements (.txt) |
| 4 | Verilog netlist (.v), Liberty file (.lib), Timing requirements (.txt) |
| 5 | All files from Mode 4 |

### Timing Requirements File Format

Create a `.txt` file with natural language timing constraints:

```
Clock period: <value> nanoseconds
Clock uncertainty: <value> nanoseconds
Input delay: <value> ns max, <value> ns min
Output delay: <value> ns max, <value> ns min
```

## Workflow

### Mode 1: Verilog Design Analysis

**Steps:**
1. Select option 1
2. Provide Verilog file path
3. Tool analyzes design structure

**Output:**
- `[design_name]_verilog_analysis.txt` - Design structure and characteristics

### Mode 2: Liberty File Analysis

**Steps:**
1. Select option 2
2. Provide Verilog file path
3. Provide Liberty file path (or use default)
4. Tool extracts and analyzes used cells

**Output:**
- `[design_name]_liberty_analysis.txt` - Cell timing and power details

### Mode 3: SDC & TCL Generation

**Steps:**
1. Select option 3
2. Provide Verilog, Liberty, and timing requirements files
3. Tool generates constraints and scripts

**Output:**
- `[design_name].sdc` - Timing constraints
- `[design_name].tcl` - OpenSTA script
- `gemini_sdc_tcl_generation.txt` - Full Gemini response

### Mode 4: Timing Analysis & Violation Fixing

**Steps:**
1. Select option 4
2. Provide Verilog, Liberty, and timing requirements files
3. Specify maximum iterations
4. Tool iteratively fixes violations

**Process:**
- Runs OpenSTA on current design
- Analyzes timing report for violations
- Applies fixing strategies using Gemini
- Documents all changes
- Repeats until violations fixed or max iterations reached

**Output:**
```
sta_violation_fixes/
├── [design_name]_design_iteration_N.v
├── [design_name]_sta_log_iteration_N.txt
└── [design_name]_gemini_response_iteration_N.txt
```

### Mode 5: Run All

**Steps:**
1. Select option 5
2. Provide all required files
3. Tool executes Modes 1-4 sequentially

**Output:**
- All outputs from Modes 1-4
- `[design_name]_best_fixed_design.v` - Best design across iterations

## Output Structure

```
Gemini_Response/OpenSTA/[design_name]/
├── [design_name]_verilog_analysis.txt
├── [design_name]_liberty_analysis.txt
├── [design_name].sdc
├── [design_name].tcl
├── [design_name].v
├── [library].lib
├── [design_name]_best_fixed_design.v
└── sta_violation_fixes/
    ├── [design_name]_design_iteration_1.v
    ├── [design_name]_sta_log_iteration_1.txt
    ├── [design_name]_gemini_response_iteration_1.txt
    ├── [design_name]_design_iteration_2.v
    └── ...
```

## Timing Fix Strategies

Applied in priority order:

1. **Cell Strength Modification** - Changes drive strength (X1 → X2 → X4)
2. **Critical Path Restructuring** - Reorganizes logic to reduce delays
3. **Selective Buffer Insertion** - Adds buffers for hold violations
4. **Combinational Logic Optimization** - Complex path modifications

## Changing Input Files

All input files can be customized at runtime:

### Verilog File
- Must be gate-level netlist (not RTL)
- Should use standard cells from Liberty file
- Can be any design size or complexity

### Liberty File
- Can use any standard cell library in Liberty format
- Nangate 45nm Open Cell Library (default)
- Or any foundry-provided library

### Timing Requirements
- Write in plain English
- Specify clock period, uncertainties, delays
- Can include any SDC-compatible constraints

### Maximum Iterations
- Default: 3
- Recommended: 3-10 based on design complexity
- More iterations = more refinement attempts

## File Path Specifications

You can provide:
- **Absolute paths**: `/full/path/to/file.v`
- **Relative paths**: `designs/file.v` (relative to working directory)
- **Press Enter** for Liberty file to use configured default

## Understanding Output Files

| File | Description |
|------|-------------|
| `verilog_analysis.txt` | Module structure, ports, logic analysis |
| `liberty_analysis.txt` | Cell timing, power, area characteristics |
| `.sdc` | Timing constraints for OpenSTA |
| `.tcl` | OpenSTA analysis script |
| `design_iteration_N.v` | Design after N iterations of fixing |
| `sta_log_iteration_N.txt` | OpenSTA timing report for iteration N |
| `gemini_response_iteration_N.txt` | LLM analysis and proposed fixes |
| `best_fixed_design.v` | Best performing design (highest slack) |

## Iteration Process Explained

Each iteration:
1. **Run STA**: Execute OpenSTA on current design
2. **Parse Report**: Extract slack values and violation details
3. **Analyze**: Send timing report to Gemini for analysis
4. **Generate Fix**: Gemini proposes design modifications
5. **Apply Changes**: Update Verilog netlist with fixes
6. **Document**: Save all changes and rationale
7. **Repeat**: Continue until violations resolved or max iterations

## Example Session

```bash
$ python lider.py

ADD YOUR GEMINI API KEY: AIza...

Enter your choice (1-5): 4

Enter the path to your Verilog design file: designs/counter.v
Enter the path to your liberty file: [press Enter for default]
Enter the path to your English SDC requirements file: constraints/counter_timing.txt
Enter the maximum number of iterations (default: 3): 5

======================================================================
Iteration 1/5
======================================================================
Running OpenSTA...
✓ OpenSTA finished successfully

Timing Status:
  Setup slack: 0.85 ps (MET)
  Hold slack: -0.08 ps (VIOLATED)

Requesting design fixes from Gemini...
Changes: Changed buffer u5 from BUF_X1 to BUF_X2

======================================================================
Iteration 2/5
======================================================================
...
```

## Limitations

- Requires internet connection for Gemini API
- Works with ASCII format files only
- Complex state machines may need manual intervention
- API rate limits may affect large designs
- Best results with designs < 1000 gates

## Troubleshooting

**OpenSTA not found:**
```bash
which sta  # Verify installation
# Update OPENSTA_PATH in script
```

**API key errors:**
- Verify key is valid at https://ai.google.dev/gemini-api
- Check for rate limiting
- Ensure internet connectivity

**Liberty file errors:**
- Ensure cells in Verilog exist in Liberty file
- Check Liberty file format compatibility
- Verify file paths are correct

## Citation

```bibtex
@article{lider2024,
  title={LIDER: A Tool Framework Leveraging Large Language Model (LLM) for Incremental Design Refinement},
  author={Shukla, Shivam and Choudhary, Utkarsh and Saurabh, Sneh},
  institution={IIIT Delhi},
  year={2024}
}
```

## Contributors

- **Shivam Shukla** - shivam22478@iiitd.ac.in
- **Utkarsh Choudhary** - utkarsh22550@iiitd.ac.in
- **Sneh Saurabh** - sneh@iiitd.ac.in

Electronics & Communication Department  
Indraprastha Institute of Information Technology, Delhi, India-110020

## License

[Specify your license here]

## Acknowledgments

- Google Gemini 2.0 Flash API
- OpenSTA by The OpenROAD Project
- Nangate Open Cell Library
