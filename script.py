import requests
import json
import os
import re
import subprocess
import shutil
import time 
import random

# ========================= CONFIGURATION =========================
OPENSTA_PATH = "/usr/local/bin/sta"
DEFAULT_LIBERTY_PATH = "/Users/utkarshchoudhary/Desktop/VDAT_Code/NangateOpenCellLibrary_typical.lib"
WORKING_DIRECTORY = "/Users/utkarshchoudhary/Desktop/VDAT_Code"

# ------------------------- Gemini API Interaction -------------------------

def query_gemini(prompt, api_key, max_retries=5, retry_delay=2, timeout=60):
    """
    Send a prompt to the Gemini API and return the response.
    Automatically retries on 503 Service Unavailable errors with exponential backoff and jitter.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=timeout)

            if response.status_code == 200:
                try:
                    return response.json()['candidates'][0]['content']['parts'][0]['text']
                except (KeyError, IndexError):
                    return "Error parsing response."

            elif response.status_code == 503:
                wait_time = retry_delay * (attempt + 1) + random.uniform(0, 1)
                print(f"⚠ Gemini API is overloaded (503). Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue

            else:
                return f"Error: {response.status_code} - {response.text}"

        except requests.exceptions.RequestException as e:
            wait_time = retry_delay * (attempt + 1) + random.uniform(0, 1)
            print(f"⚠ Network error: {e}. Retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)

    return "⚠ Gemini API unavailable. Please try again later."

# ------------------------- OpenSTA Automation -------------------------

def run_opensta(tcl_file, log_file, opensta_path=OPENSTA_PATH):
    """Execute OpenSTA with the given TCL script and capture output to log file."""
    try:
        tcl_file = os.path.abspath(tcl_file)
        log_file = os.path.abspath(log_file)
        tcl_dir = os.path.dirname(tcl_file)
        
        print(f"\nRunning OpenSTA command:")
        print(f"cd {tcl_dir} && {opensta_path} -exit {os.path.basename(tcl_file)}\n")
        
        cmd = f"cd {tcl_dir} && {opensta_path} -exit {os.path.basename(tcl_file)}"
        
        with open(log_file, "w") as logfile:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=logfile,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
        
        log_content = read_file(log_file)
        
        if result.returncode == 0:
            print(f"✓ OpenSTA finished successfully. Output saved to:\n{log_file}\n")
            return True, log_content
        else:
            print(f"✗ OpenSTA encountered an error. Return code: {result.returncode}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
            print(f"Check the log at:\n{log_file}\n")
            return False, log_content
            
    except Exception as e:
        print(f"✗ Exception occurred while running OpenSTA: {e}")
        return False, None
    
# ------------------------- File Handling -------------------------

def read_file(file_path):
    """Read a file and return its contents as a string."""
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def write_file(file_path, content):
    """Write content to a file."""
    try:
        with open(file_path, 'w', encoding="utf-8") as file:
            file.write(content)
        print(f"✓ Successfully wrote to {file_path}")
        return True
    except Exception as e:
        print(f"✗ Error writing to file {file_path}: {e}")
        return False

# ------------------------- Gemini Analysis Functions -------------------------

def analyze_verilog_with_gemini(design_content, api_key):
    """Use Gemini API to analyze a Verilog design file."""
    prompt = f"""
You are an expert in ASIC design and Verilog HDL. I need a detailed analysis of the following Verilog design.
Please provide a comprehensive report that includes:

1. The module name and its purpose
2. Identification of all input and output ports with their bit widths
3. Analysis of sequential elements (flip-flops, registers)
4. Analysis of combinational logic (gates, assignments)
5. Identification of clock domains and reset signals
6. Detection of state machines if present
7. Analysis of timing paths between flip-flops
8. Identification of potential critical paths
9. Overall design architecture and functionality

Here is the Verilog design:

```verilog
{design_content}
```

Provide your analysis in a structured, detailed report format.
"""
    return query_gemini(prompt, api_key)

def analyze_liberty_with_gemini(design_content, liberty_content, api_key):
    """Use Gemini API to analyze cells in a Liberty file that are used in the Verilog design."""
    prompt = f"""
You are an expert in ASIC design, Liberty format (.lib files), and Verilog HDL. 

I need you to perform a comprehensive analysis of the Liberty file cells that are used in the provided Verilog design.

Your task involves:
1. First, identify all standard cells that are instantiated or used in the Verilog design, identify their instances it is used in the verilog design and count how many instances used and report them so those wil be the number of times that particular cell is used.
2. For each identified cell, find its definition in the Liberty file
3. Analyze each cell's characteristics including:
   - Cell function and purpose
   - Input and output pins
   - Timing characteristics (delay arcs, setup/hold times)
   - Power information
   - Area and physical properties
   - Any other relevant attributes

Here is the Verilog design:
```verilog
{design_content}
```

Here is the Liberty file (note that it might be large, so analyze what you can with the provided content):
```liberty
{liberty_content[:100000]}
```

Please provide a detailed analysis focusing specifically on the cells that appear in the Verilog design.
If the Liberty file is truncated and you cannot find a specific cell, please mention this in your analysis.
"""
    return query_gemini(prompt, api_key)

# ------------------------- SDC and TCL Extraction -------------------------

def extract_sdc_code(response):
    """Extract SDC code from Gemini's response."""
    sdc_match = re.search(r'```sdc\s*([\s\S]*?)\s*```', response)
    if sdc_match:
        return sdc_match.group(1).strip()
    
    alt_match = re.search(r'<sdc>\s*([\s\S]*?)\s*</sdc>', response)
    if alt_match:
        return alt_match.group(1).strip()
    
    code_block = re.search(r'```\s*([\s\S]*?)\s*```', response)
    if code_block:
        return code_block.group(1).strip()
    
    return response.strip()

def extract_tcl_code(response):
    """Extract TCL code from Gemini's response."""
    tcl_match = re.search(r'```tcl\s*([\s\S]*?)\s*```', response)
    if tcl_match:
        return tcl_match.group(1).strip()
    
    alt_match = re.search(r'<tcl>\s*([\s\S]*?)\s*</tcl>', response)
    if alt_match:
        return alt_match.group(1).strip()
    
    code_block = re.search(r'```\s*([\s\S]*?)\s*```', response)
    if code_block and "read_verilog" in code_block.group(1):
        return code_block.group(1).strip()
    
    return None

def extract_verilog_code(response):
    """Extract Verilog code from Gemini's response."""
    verilog_match = re.search(r'```verilog\s*([\s\S]*?)\s*```', response)
    if verilog_match:
        return verilog_match.group(1).strip()
    
    alt_match = re.search(r'<verilog>\s*([\s\S]*?)\s*</verilog>', response)
    if alt_match:
        return alt_match.group(1).strip()
    
    module_match = re.search(r'(module\s+\w+[\s\S]*?endmodule)', response)
    if module_match:
        return module_match.group(1).strip()
    
    return None

# ------------------------- SDC and TCL Post-Processing -------------------------

def post_process_sdc(sdc_content, sdc_requirement):
    """Post-process the SDC file to remove unnecessary commands and fix common issues."""
    lines = sdc_content.strip().split('\n')
    processed_lines = []
    seen_commands = set()
    
    for line in lines:
        stripped = line.strip()
        if not stripped or (stripped.startswith('#') and 
                           any(x in stripped.lower() for x in ['file for', 'section', 'definition', 'delay', 'load'])):
            continue
        
        if stripped.startswith('# set_') or stripped.startswith('# create_'):
            continue
            
        cmd_match = re.match(r'(\w+)\s+([^-\s]+)', stripped)
        if cmd_match and not stripped.startswith('#'):
            cmd_type = cmd_match.group(1)
            cmd_key = f"{cmd_type}:{stripped}"
            if cmd_key in seen_commands:
                continue
            seen_commands.add(cmd_key)
        
        # Do NOT convert units - keep exactly what Gemini returns
        # Gemini is already instructed to use the correct units from requirements
        
        if 'set_driving_cell' in stripped and 'drive' not in sdc_requirement.lower():
            continue
        if 'set_load' in stripped and 'load' not in sdc_requirement.lower():
            continue
        
        processed_lines.append(stripped)
    
    return '\n'.join(processed_lines)

def post_process_tcl(tcl_content, design_name, sdc_file, liberty_file):
    """Post-process the TCL script."""
    template = f"""
# Read liberty file
read_liberty {liberty_file}

# Read the design file
read_verilog {design_name}.v

# Link the design
link_design {design_name}

# Read the SDC constraints
read_sdc {os.path.basename(sdc_file)}

# Report setup path (max delay)
puts "\\nSetup Path Analysis:"
report_checks -path_delay max

# Report hold path (min delay)
puts "\\nHold Path Analysis:"
report_checks -path_delay min

# Exit OpenSTA
exit
"""
    return template

def create_default_tcl(design_file, sdc_file, liberty_file, design_name):
    """Create a default TCL script."""
    design_path = os.path.basename(design_file)
    sdc_path = os.path.basename(sdc_file)
    
    return f"""
# Read liberty file
read_liberty {liberty_file}

# Read the design file
read_verilog {design_path}

# Link the design
link_design {design_name}

# Read the SDC constraints
read_sdc {sdc_path}

# Report timing checks
report_checks -path_delay max
report_checks -path_delay min

# Exit OpenSTA
exit
"""

def get_top_module_name(design_content):
    """Extract the top module name from Verilog design content."""
    pattern = r'module\s+(\w+)'
    match = re.search(pattern, design_content)
    if match:
        return match.group(1)
    return "top_module"

# ------------------------- Prompt Creation -------------------------

def create_initial_prompt(design_content, sdc_requirement, liberty_file):
    """Generate initial prompt for Gemini to create SDC and TCL files."""
    clock_period_match = re.search(r'clock\s+period\s+(\d+\.?\d*)', sdc_requirement, re.IGNORECASE)
    clock_period = clock_period_match.group(1) if clock_period_match else "UNKNOWN"
    
    uncertainty_match = re.search(r'uncertainty\s+of\s+(\d+\.?\d*)', sdc_requirement, re.IGNORECASE)
    uncertainty = uncertainty_match.group(1) if uncertainty_match else "UNKNOWN"
    
    return f"""
As an expert in Static Timing Analysis (STA), I need to generate an SDC file and a TCL script for OpenSTA based on the following Verilog design and specific timing requirements.

## Verilog Design
```verilog
{design_content}
```

## SPECIFIC Timing Requirements - FOLLOW THESE EXACTLY
{sdc_requirement}

## IMPORTANT INSTRUCTIONS FOR SDC FILE:
- ONLY include commands that are absolutely necessary based on the requirements.
- Use the EXACT time values and units specified in the requirements above.
- For clock period, use exactly this format if needed: create_clock -name CLK -period {clock_period} [get_ports CLK]
- For clock uncertainty, use exactly this format if needed: set_clock_uncertainty {uncertainty} [get_clocks CLK]
- DO NOT include commented-out commands or extra comments except basic descriptions.
- DO NOT include any commands related to load or drive strength unless specifically requested.

## IMPORTANT INSTRUCTIONS FOR TCL SCRIPT:
- The TCL script must follow EXACTLY this structure:
  1. read_liberty {liberty_file}
  2. read_verilog [design_file].v
  3. link_design [top_module]
  4. read_sdc [sdc_file]
  5. Only the specific timing reports asked for in the requirements
  6. exit

Please provide:
1. An SDC file inside ```sdc and ``` tags that follows the specified format.
2. A TCL script inside ```tcl and ``` tags that follows the specified format.
"""

# ------------------------- Cell Extraction -------------------------

def extract_used_cells_from_verilog(verilog: str):
    """Extract all unique standard cell types used in the Verilog file."""
    pattern = re.compile(r'^\s*(\w+)\s+\w+\s*\(', re.MULTILINE)
    used = sorted(set(pattern.findall(verilog)))
    return [cell for cell in used if cell.lower() != "module"]

def extract_cells_from_liberty(liberty: str, target_cells: list) -> str:
    """Extract complete cell blocks for only the used cells."""

    result = []
    inside_cell = False
    brace_count = 0
    current_block = []

    for line in liberty.splitlines():
        line_stripped = line.strip()

        if not inside_cell:
            match = re.match(r'cell\s*\(\s*"?(\w+)"?\s*\)\s*\{', line_stripped)
            if match:
                cell_name = match.group(1)
                if cell_name in target_cells:
                    inside_cell = True
                    brace_count = 1
                    current_block = [line]
                continue

        elif inside_cell:
            brace_count += line.count('{') - line.count('}')
            current_block.append(line)
            if brace_count == 0:
                result.append('\n'.join(current_block))
                inside_cell = False
                current_block = []

    return '\n\n'.join(result)

def get_minimal_liberty_for_timing_fixes(verilog: str, liberty: str) -> str:
    """Extract minimal cell information needed for timing fixes."""
    used_cells = extract_used_cells_from_verilog(verilog)
    return extract_cells_from_liberty(liberty, used_cells)

# ------------------------- Timing Violation Detection -------------------------

def parse_log_for_timing_violations(log_content):
    """Parse the OpenSTA log to identify setup and hold violations."""
    violations = {
        'setup': [],
        'hold': [],
        'has_violations': False,
        'worst_setup_slack': None,
        'worst_hold_slack': None,
    }
    
    violated_matches = re.findall(r'(-?\d+\.\d+)\s+slack\s+\(VIOLATED\)', log_content)
    if violated_matches:
        violations['has_violations'] = True
    
    setup_sections = re.findall(r'Path Type: max(.*?)(?:Path Type:|$)', log_content, re.DOTALL)
    for section in setup_sections:
        slack_match = re.search(r'(-?\d+\.\d+)\s+slack', section)
        if slack_match:
            slack = float(slack_match.group(1))
            if violations['worst_setup_slack'] is None or slack < violations['worst_setup_slack']:
                violations['worst_setup_slack'] = slack
            
            if slack < 0 or "VIOLATED" in section:
                violations['has_violations'] = True
                violations['setup'].append({'slack': slack})
    
    hold_sections = re.findall(r'Path Type: min(.*?)(?:Path Type:|$)', log_content, re.DOTALL)
    for section in hold_sections:
        slack_match = re.search(r'(-?\d+\.\d+)\s+slack', section)
        if slack_match:
            slack = float(slack_match.group(1))
            if violations['worst_hold_slack'] is None or slack < violations['worst_hold_slack']:
                violations['worst_hold_slack'] = slack
            
            if slack < 0 or "VIOLATED" in section:
                violations['has_violations'] = True
                violations['hold'].append({'slack': slack})
    
    return violations

# ------------------------- Timing Violation Fixing -------------------------

def fix_timing_violations_with_gemini(design_content, timing_analysis, liberty_content, api_key, 
                                     fix_history=None, iteration=1, violations_history=None):
    """Use Gemini API to generate fixes for timing violations in the design."""
    if iteration == 1 or not fix_history:
        prompt = f"""
You are an expert in ASIC design, Verilog HDL, and static timing analysis. I need you to fix timing violations in a Verilog design based on OpenSTA timing analysis.

First, examine the current Verilog design:
```verilog
{design_content}
```

Now, examine the timing analysis report identifying violations:
```
{timing_analysis}
```

I also provide the Liberty file for reference (partial):
```liberty
{liberty_content[:50000]}
```

Based on these, please:

1. Identify all timing violations (setup and hold) in the design
2. Determine the best approach to fix each violation
3. Implement the fixes directly in the Verilog code
4. Use techniques like:
   - Cell resizing (changing drive strength) 
   - Inserting buffer cells 
   - Adding delay cells 
   - Restructuring critical paths


Provide the COMPLETE updated Verilog design with all fixes implemented.

Include detailed comments explaining:
1. What violations were identified
2. What fixes were applied and why
3. How each fix addresses the specific timing issue

Format your response with the modified Verilog code inside ```verilog and ``` tags.
"""
    else:
        violation_trend = ""
        if violations_history and len(violations_history) >= 2:
            current = violations_history[-1]
            previous = violations_history[-2]
            
            setup_trend = "IMPROVED" if current['worst_setup_slack'] > previous['worst_setup_slack'] else "WORSENED"
            hold_trend = "IMPROVED" if not current.get('worst_hold_slack') or (current['worst_hold_slack'] > previous.get('worst_hold_slack', 0)) else "WORSENED"
            
            violation_trend = f"""
VIOLATION TREND ANALYSIS:
- Setup slack: Previous={previous['worst_setup_slack']} ps → Current={current['worst_setup_slack']} ps ({setup_trend})
- Hold slack: Previous={previous.get('worst_hold_slack', 'NO VIOLATION')} ps → Current={current.get('worst_hold_slack', 'NO VIOLATION')} ps ({hold_trend})

Your previous changes have {setup_trend.lower()} setup timing and {hold_trend.lower()} hold timing.
"""
        
        history_context = "DESIGN MODIFICATION HISTORY:\n"
        for i, hist in enumerate(fix_history):
            history_context += f"Iteration {i+1}:\n"
            history_context += f"- Changes: {hist['changes']}\n"
            history_context += f"- Results: Setup={hist['setup_slack']} ps, Hold={hist.get('hold_slack', 'NO VIOLATION')} ps\n\n"
        
        best_iteration = 0
        best_setup_slack = -float('inf')
        for i, hist in enumerate(fix_history):
            if hist['setup_slack'] > best_setup_slack:
                best_setup_slack = hist['setup_slack']
                best_iteration = i
        
        best_design = fix_history[best_iteration]['design']
        current_design = fix_history[-1]['design']
        
        prompt = f"""
You are an expert in ASIC design, Verilog HDL, and static timing analysis.

ITERATION {iteration}: Previous fixes have been applied but violations still exist.

{violation_trend}

**Original Design:**
```verilog
{design_content[:20000]}
```

**Most Successful Design (Iteration {best_iteration+1}):**
```verilog
{best_design}
```

**Current Design (Iteration {iteration-1}):**
```verilog
{current_design}
```

{history_context}

**Current Timing Analysis Report:**
```
{timing_analysis[:10000]}
```

**Liberty File Reference (partial):**
```liberty
{liberty_content[:30000]}
```

Based on this:

1. Analyze what went wrong with previous fixes
2. Identify remaining timing violations
3. Consider using the most successful design version as your starting point
4. Make very targeted changes

CRITICALLY IMPORTANT:
1. If previous changes worsened setup time, DO NOT add more buffers
2. Focus on high-drive strength cells (e.g., X2, X4) for critical setup path
3. Make smaller, more focused changes
4. Explain why your changes should improve the situation

Provide the COMPLETE updated Verilog design inside ```verilog and ``` tags.
"""
    return query_gemini(prompt, api_key)

def summarize_changes(original_design, new_design):
    """Generate a summary of changes between original and new design."""
    def extract_instantiations(design):
        instantiations = {}
        pattern = r'(\w+)_X(\d+)\s+(\w+)\s*\('
        matches = re.finditer(pattern, design)
        for match in matches:
            cell_type = match.group(1)
            drive_strength = match.group(2)
            instance_name = match.group(3)
            instantiations[instance_name] = {
                'type': cell_type,
                'strength': drive_strength
            }
        return instantiations
    
    orig_inst = extract_instantiations(original_design)
    new_inst = extract_instantiations(new_design)
    
    changes = []
    
    for inst_name, orig_info in orig_inst.items():
        if inst_name in new_inst:
            new_info = new_inst[inst_name]
            if orig_info != new_info:
                changes.append(f"Changed {inst_name} from {orig_info['type']}_X{orig_info['strength']} to {new_info['type']}_X{new_info['strength']}")
    
    for inst_name, new_info in new_inst.items():
        if inst_name not in orig_inst:
            changes.append(f"Added {inst_name} ({new_info['type']}_X{new_info['strength']})")
    
    for inst_name in orig_inst:
        if inst_name not in new_inst:
            changes.append(f"Removed {inst_name}")
    
    return "; ".join(changes) if changes else "No significant changes detected"

# ------------------------- Main Function -------------------------

def main():
    print("=" * 80)
    print("OpenSTA Automation with Gemini API")
    print("=" * 80)
    
    api_key = input("ADD YOUR GEMINI API KEY")
    
    print("\nWhat help do you want from our tool?")
    print("Options:")
    print("1) Verilog Design Analysis")
    print("2) Liberty File Analysis for Design Cells")
    print("3) SDC & TCL Generation")
    print("4) Timing Analysis & Violation Fixing (Combined)")
    print("5) Run all")
    
    choice = input("\nEnter your choice (1-5): ")
    
    base_dir = os.path.join("Gemini_Response", "OpenSTA")
    os.makedirs(base_dir, exist_ok=True)
    
    if choice == "1":  # Verilog Design Analysis
        design_file = input("Enter the path to your Verilog design file: ")
        design_content = read_file(design_file)
        
        if not design_content:
            print("Error: Could not read design file. Exiting.")
            return
        
        design_name = os.path.splitext(os.path.basename(design_file))[0]
        design_dir = os.path.join(base_dir, design_name)
        os.makedirs(design_dir, exist_ok=True)
        
        print("\n" + "=" * 80)
        print("Verilog Design Analysis")
        print("=" * 80)
        
        print("Requesting Verilog analysis from Gemini...")
        verilog_analysis = analyze_verilog_with_gemini(design_content, api_key)
        
        verilog_analysis_file = os.path.join(design_dir, f"{design_name}_verilog_analysis.txt")
        write_file(verilog_analysis_file, verilog_analysis)
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Analysis saved to: {verilog_analysis_file}")
    
    elif choice == "2":  # Liberty File Analysis
        design_file = input("Enter the path to your Verilog design file: ")
        liberty_file = input("Enter the path to your liberty file (default: NangateOpenCellLibrary_typical.lib): ")
        if not liberty_file:
            liberty_file = "NangateOpenCellLibrary_typical.lib"
        
        design_content = read_file(design_file)
        liberty_content = read_file(liberty_file)
        
        if not design_content or not liberty_content:
            print("Error: Could not read required files. Exiting.")
            return
        
        design_name = os.path.splitext(os.path.basename(design_file))[0]
        design_dir = os.path.join(base_dir, design_name)
        os.makedirs(design_dir, exist_ok=True)
        
        print("\n" + "=" * 80)
        print("Liberty File Analysis")
        print("=" * 80)
        
        # Filter liberty file
        filtered_lib = get_minimal_liberty_for_timing_fixes(design_content, liberty_content)
        liberty_content = filtered_lib
        
        print("Requesting Liberty file analysis from Gemini...")
        liberty_analysis = analyze_liberty_with_gemini(design_content, liberty_content, api_key)
        
        liberty_analysis_file = os.path.join(design_dir, f"{design_name}_liberty_analysis.txt")
        write_file(liberty_analysis_file, liberty_analysis)
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Analysis saved to: {liberty_analysis_file}")
    
    elif choice == "3":  # SDC & TCL Generation
        design_file = input("Enter the path to your Verilog design file: ")
        liberty_file = input("Enter the path to your liberty file (default: NangateOpenCellLibrary_typical.lib): ")
        if not liberty_file:
            liberty_file = "NangateOpenCellLibrary_typical.lib"
        sdc_requirement_file = input("Enter the path to your English SDC requirements file: ")
        
        design_content = read_file(design_file)
        liberty_content = read_file(liberty_file)
        sdc_requirement = read_file(sdc_requirement_file)
        
        if not design_content or not liberty_content or not sdc_requirement:
            print("Error: Could not read required files. Exiting.")
            return
        
        design_name = os.path.splitext(os.path.basename(design_file))[0]
        design_dir = os.path.join(base_dir, design_name)
        os.makedirs(design_dir, exist_ok=True)
        
        print("\n" + "=" * 80)
        print("SDC & TCL Generation")
        print("=" * 80)
        
        output_design_file = os.path.join(design_dir, os.path.basename(design_file))
        sdc_file = os.path.join(design_dir, f"{design_name}.sdc")
        tcl_file = os.path.join(design_dir, f"{design_name}.tcl")
        
        liberty_name = os.path.splitext(os.path.basename(liberty_file))[0]
        
        # Copy files
        if not os.path.exists(output_design_file):
            shutil.copy2(design_file, output_design_file)
        shutil.copy2(liberty_file, os.path.join(design_dir, liberty_name + ".lib"))
        
        # Generate SDC and TCL
        top_module = get_top_module_name(design_content)
        liberty_filename = os.path.basename(liberty_file)
        
        prompt = create_initial_prompt(design_content, sdc_requirement, liberty_filename)
        print("Generating SDC and TCL files using Gemini...")
        
        response = query_gemini(prompt, api_key)
        
        sdc_code = extract_sdc_code(response)
        tcl_code = extract_tcl_code(response)
        
        sdc_code = post_process_sdc(sdc_code, sdc_requirement)
        
        if not tcl_code or liberty_filename not in tcl_code:
            tcl_code = create_default_tcl(os.path.basename(output_design_file), 
                                       os.path.basename(sdc_file), 
                                       liberty_filename,
                                       top_module)
        else:
            tcl_code = post_process_tcl(tcl_code, top_module, 
                                    os.path.basename(sdc_file), 
                                    liberty_filename)
        
        write_file(sdc_file, sdc_code)
        write_file(tcl_file, tcl_code)
        
        response_file = os.path.join(design_dir, f"gemini_sdc_tcl_generation.txt")
        write_file(response_file, response)
        
        print("\n" + "=" * 80)
        print("GENERATION COMPLETE")
        print("=" * 80)
        print(f"Files saved to: {design_dir}")
        print(f"  - SDC: {design_name}.sdc")
        print(f"  - TCL: {design_name}.tcl")
        print(f"  - Gemini Response: gemini_sdc_tcl_generation.txt")
    
    elif choice == "4":  # Timing Analysis & Violation Fixing
        design_file = input("Enter the path to your Verilog design file: ")
        liberty_file = input("Enter the path to your liberty file (default: NangateOpenCellLibrary_typical.lib): ")
        if not liberty_file:
            liberty_file = "NangateOpenCellLibrary_typical.lib"
        sdc_requirement_file = input("Enter the path to your English SDC requirements file: ")
        
        design_content = read_file(design_file)
        liberty_content = read_file(liberty_file)
        filtered_lib = get_minimal_liberty_for_timing_fixes(design_content, liberty_content)
        liberty_content = filtered_lib
        sdc_requirement = read_file(sdc_requirement_file)
        
        if not design_content or not liberty_content or not sdc_requirement:
            print("Error: Could not read required files. Exiting.")
            return
        
        design_name = os.path.splitext(os.path.basename(design_file))[0]
        design_dir = os.path.join(base_dir, design_name)
        os.makedirs(design_dir, exist_ok=True)
        
        # Generate SDC and TCL files first
        output_design_file = os.path.join(design_dir, os.path.basename(design_file))
        sdc_file = os.path.join(design_dir, f"{design_name}.sdc")
        tcl_file = os.path.join(design_dir, f"{design_name}.tcl")
        
        liberty_name = os.path.splitext(os.path.basename(liberty_file))[0]
        
        if not os.path.exists(output_design_file):
            shutil.copy2(design_file, output_design_file)
        shutil.copy2(liberty_file, os.path.join(design_dir, liberty_name + ".lib"))
        
        top_module = get_top_module_name(design_content)
        liberty_filename = os.path.basename(liberty_file)
        
        # Check if SDC and TCL already exist, otherwise generate
        if not os.path.exists(sdc_file) or not os.path.exists(tcl_file):
            print("Generating SDC and TCL files...")
            prompt = create_initial_prompt(design_content, sdc_requirement, liberty_filename)
            response = query_gemini(prompt, api_key)
            
            sdc_code = extract_sdc_code(response)
            tcl_code = extract_tcl_code(response)
            
            sdc_code = post_process_sdc(sdc_code, sdc_requirement)
            
            if not tcl_code or liberty_filename not in tcl_code:
                tcl_code = create_default_tcl(os.path.basename(output_design_file), 
                                           os.path.basename(sdc_file), 
                                           liberty_filename,
                                           top_module)
            else:
                tcl_code = post_process_tcl(tcl_code, top_module, 
                                        os.path.basename(sdc_file), 
                                        liberty_filename)
            
            write_file(sdc_file, sdc_code)
            write_file(tcl_file, tcl_code)
        
        print("\n" + "=" * 80)
        print("Timing Analysis & Violation Fixing")
        print("=" * 80)
        
        # Ask for iterations
        try:
            num_iterations = int(input("Enter the maximum number of iterations (default: 3): ") or 3)
        except ValueError:
            num_iterations = 3
        
        iterations_dir = os.path.join(design_dir, "sta_violation_fixes")
        os.makedirs(iterations_dir, exist_ok=True)
        
        original_design = design_content
        current_design = design_content
        fix_history = []
        violations_history = []
        
        for iteration in range(1, num_iterations + 1):
            print(f"\n{'='*70}")
            print(f"Iteration {iteration}/{num_iterations}")
            print(f"{'='*70}")
            
            design_iter_file = os.path.join(iterations_dir, f"{design_name}_design_iteration_{iteration}.v")
            write_file(design_iter_file, current_design)
            
            write_file(output_design_file, current_design)
            
            log_file = os.path.join(iterations_dir, f"{design_name}_sta_log_iteration_{iteration}.txt")
            success, log_content = run_opensta(tcl_file, log_file)
            
            if not success or not log_content:
                print(f"✗ OpenSTA failed. Stopping.")
                break
            
            violations = parse_log_for_timing_violations(log_content)
            violations_history.append(violations)
            
            print(f"\nTiming Status:")
            if violations['worst_setup_slack'] is not None:
                status = "VIOLATED" if violations['worst_setup_slack'] < 0 else "MET"
                print(f"  Setup slack: {violations['worst_setup_slack']} ps ({status})")
            if violations['worst_hold_slack'] is not None:
                status = "VIOLATED" if violations['worst_hold_slack'] < 0 else "MET"
                print(f"  Hold slack: {violations['worst_hold_slack']} ps ({status})")
            
            if not violations['has_violations']:
                print(f"\n✓ All violations fixed!")
                break
            
            if iteration >= num_iterations:
                print(f"\n⚠ Maximum iterations reached.")
                break
            
            print(f"\nRequesting fixes from Gemini...")
            
            fixed_design_response = fix_timing_violations_with_gemini(
                original_design, log_content, liberty_content, api_key,
                fix_history=fix_history, iteration=iteration,
                violations_history=violations_history
            )
            
            response_file = os.path.join(iterations_dir, f"{design_name}_gemini_response_iteration_{iteration}.txt")
            write_file(response_file, fixed_design_response)
            
            extracted_verilog = extract_verilog_code(fixed_design_response)
            
            if not extracted_verilog:
                print("⚠ Could not extract Verilog code.")
                break
            
            changes_summary = summarize_changes(current_design, extracted_verilog)
            print(f"Changes: {changes_summary}")
            
            current_design = extracted_verilog
            
            fix_history.append({
                'design': extracted_verilog,
                'changes': changes_summary,
                'setup_slack': violations['worst_setup_slack'],
                'hold_slack': violations['worst_hold_slack']
            })
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Files saved to: {iterations_dir}")
    
    elif choice == "5":  # Run all
        # Collect all required files
        design_file = input("Enter the path to your Verilog design file: ")
        liberty_file = input("Enter the path to your liberty file (default: NangateOpenCellLibrary_typical.lib): ")
        if not liberty_file:
            liberty_file = "NangateOpenCellLibrary_typical.lib"
        sdc_requirement_file = input("Enter the path to your English SDC requirements file: ")
        
        # Read file contents
        design_content = read_file(design_file)
        liberty_content = read_file(liberty_file)
        filtered_lib = get_minimal_liberty_for_timing_fixes(design_content, liberty_content)
        write_file("liberty_shortened.lib", filtered_lib)
        liberty_content = filtered_lib

        sdc_requirement = read_file(sdc_requirement_file)
        
        if not design_content or not liberty_content or not sdc_requirement:
            print("Error: Could not read required files. Exiting.")
            return
        
        # Create design-specific directory
        design_name = os.path.splitext(os.path.basename(design_file))[0]
        design_dir = os.path.join(base_dir, design_name)
        os.makedirs(design_dir, exist_ok=True)
        
        # ==================== STEP 1: Verilog Design Analysis ====================
        print("\n" + "=" * 80)
        print("STEP 1: Verilog Design Analysis")
        print("=" * 80)
        
        print("Requesting Verilog analysis from Gemini...")
        verilog_analysis = analyze_verilog_with_gemini(design_content, api_key)
        
        verilog_analysis_file = os.path.join(design_dir, f"{design_name}_verilog_analysis.txt")
        write_file(verilog_analysis_file, verilog_analysis)
        
        print("\nVerilog Analysis Preview:")
        print("-" * 40)
        preview_length = min(500, len(verilog_analysis))
        print(verilog_analysis[:preview_length] + "..." if len(verilog_analysis) > preview_length else verilog_analysis)
        print("-" * 40)
        
        # ==================== STEP 2: Liberty File Analysis ====================
        print("\n" + "=" * 80)
        print("STEP 2: Liberty File Analysis")
        print("=" * 80)
        
        print("Requesting Liberty file analysis from Gemini...")
        liberty_analysis = analyze_liberty_with_gemini(design_content, liberty_content, api_key)
        
        liberty_analysis_file = os.path.join(design_dir, f"{design_name}_liberty_analysis.txt")
        write_file(liberty_analysis_file, liberty_analysis)
        
        print("\nLiberty Analysis Preview:")
        print("-" * 40)
        preview_length = min(500, len(liberty_analysis))
        print(liberty_analysis[:preview_length] + "..." if len(liberty_analysis) > preview_length else liberty_analysis)
        print("-" * 40)
        
        # ==================== STEP 3: SDC & TCL Generation ====================
        print("\n" + "=" * 80)
        print("STEP 3: SDC & TCL Generation (No STA Yet)")
        print("=" * 80)
        
        output_design_file = os.path.join(design_dir, os.path.basename(design_file))
        sdc_file = os.path.join(design_dir, f"{design_name}.sdc")
        tcl_file = os.path.join(design_dir, f"{design_name}.tcl")

        liberty_name = os.path.splitext(os.path.basename(liberty_file))[0]

        # Copy files
        if not os.path.exists(output_design_file):
            shutil.copy2(design_file, output_design_file)
            print(f"Copied design file to {output_design_file}")
        shutil.copy2(liberty_file, os.path.join(design_dir, liberty_name + ".lib"))
        print(f"Copied liberty file to {os.path.join(design_dir, liberty_name + '.lib')}")
        
        # Generate SDC and TCL files
        top_module = get_top_module_name(design_content)
        liberty_filename = os.path.basename(liberty_file)
        
        prompt = create_initial_prompt(design_content, sdc_requirement, liberty_filename)
        print("Generating initial SDC and TCL files using Gemini...")
        
        response = query_gemini(prompt, api_key)
        
        sdc_code = extract_sdc_code(response)
        tcl_code = extract_tcl_code(response)
        
        sdc_code = post_process_sdc(sdc_code, sdc_requirement)
        
        if not tcl_code or liberty_filename not in tcl_code:
            tcl_code = create_default_tcl(os.path.basename(output_design_file), 
                                       os.path.basename(sdc_file), 
                                       liberty_filename,
                                       top_module)
        else:
            tcl_code = post_process_tcl(tcl_code, top_module, 
                                    os.path.basename(sdc_file), 
                                    liberty_filename)
        
        write_file(sdc_file, sdc_code)
        write_file(tcl_file, tcl_code)
        
        response_file = os.path.join(design_dir, f"gemini_sdc_tcl_generation.txt")
        write_file(response_file, response)
        
        print(f"\n✓ SDC & TCL files generated in {design_dir}")
        
        # ==================== STEP 4: Combined STA & Violation Fixing ====================
        print("\n" + "=" * 80)
        print("STEP 4: Static Timing Analysis & Violation Fixing (Combined)")
        print("=" * 80)
        
        # Ask for number of iterations
        try:
            num_iterations = int(input("Enter the maximum number of iterations (default: 3): ") or 3)
        except ValueError:
            num_iterations = 3
            print("Invalid input. Using default value of 3 iterations.")
        
        # Create subdirectory for iterations
        iterations_dir = os.path.join(design_dir, "sta_violation_fixes")
        os.makedirs(iterations_dir, exist_ok=True)
        
        # Track history
        original_design = design_content
        current_design = design_content
        fix_history = []
        violations_history = []
        
        # Run iterative STA + violation fixing
        for iteration in range(1, num_iterations + 1):
            print(f"\n{'='*70}")
            print(f"Iteration {iteration}/{num_iterations}")
            print(f"{'='*70}")
            
            # Save current design to iterations directory
            design_iter_file = os.path.join(iterations_dir, f"{design_name}_design_iteration_{iteration}.v")
            write_file(design_iter_file, current_design)
            print(f"Saved design: {os.path.basename(design_iter_file)}")
            
            # Update main design file for OpenSTA
            write_file(output_design_file, current_design)
            
            # Run OpenSTA
            log_file = os.path.join(iterations_dir, f"{design_name}_sta_log_iteration_{iteration}.txt")
            success, log_content = run_opensta(tcl_file, log_file)
            
            if not success or not log_content:
                print(f"✗ OpenSTA execution failed in iteration {iteration}. Stopping.")
                break
            
            print(f"Saved STA log: {os.path.basename(log_file)}")
            
            # Parse for violations
            violations = parse_log_for_timing_violations(log_content)
            violations_history.append(violations)
            
            # Display violation status
            print(f"\nTiming Status:")
            if violations['worst_setup_slack'] is not None:
                status = "VIOLATED" if violations['worst_setup_slack'] < 0 else "MET"
                print(f"  Setup slack: {violations['worst_setup_slack']} ps ({status})")
            if violations['worst_hold_slack'] is not None:
                status = "VIOLATED" if violations['worst_hold_slack'] < 0 else "MET"
                print(f"  Hold slack: {violations['worst_hold_slack']} ps ({status})")
            
            # Check if violations are fixed
            if not violations['has_violations']:
                print(f"\n✓ SUCCESS: All timing violations fixed in iteration {iteration}!")
                print(f"\n✓ Files saved for iteration {iteration}:")
                print(f"  - Design: {os.path.basename(design_iter_file)}")
                print(f"  - STA Log: {os.path.basename(log_file)}")
                break
            
            # If last iteration, stop
            if iteration >= num_iterations:
                print(f"\n⚠ Reached maximum iterations ({num_iterations}). Violations remain.")
                print(f"\n✓ Files saved for iteration {iteration}:")
                print(f"  - Design: {os.path.basename(design_iter_file)}")
                print(f"  - STA Log: {os.path.basename(log_file)}")
                break
            
            # Request fixes from Gemini
            print(f"\nRequesting design fixes from Gemini for iteration {iteration+1}...")
            
            fixed_design_response = fix_timing_violations_with_gemini(
                original_design, 
                log_content, 
                liberty_content, 
                api_key,
                fix_history=fix_history,
                iteration=iteration,
                violations_history=violations_history
            )
            
            # Save Gemini response
            response_file = os.path.join(iterations_dir, f"{design_name}_gemini_response_iteration_{iteration}.txt")
            write_file(response_file, fixed_design_response)
            print(f"Saved Gemini response: {os.path.basename(response_file)}")
            
            # Extract fixed Verilog code
            extracted_verilog = extract_verilog_code(fixed_design_response)
            
            if not extracted_verilog:
                print("⚠ Warning: Could not extract Verilog code from Gemini's response.")
                break
            
            # Summarize changes
            changes_summary = summarize_changes(current_design, extracted_verilog)
            print(f"Changes: {changes_summary}")
            
            # Update current design
            current_design = extracted_verilog
            
            # Add to history
            fix_history.append({
                'design': extracted_verilog,
                'changes': changes_summary,
                'setup_slack': violations['worst_setup_slack'],
                'hold_slack': violations['worst_hold_slack']
            })
            
            print(f"\n✓ Files saved for iteration {iteration}:")
            print(f"  - Design: {os.path.basename(design_iter_file)}")
            print(f"  - STA Log: {os.path.basename(log_file)}")
            print(f"  - Gemini Response: {os.path.basename(response_file)}")
        
        # Determine best iteration
        if fix_history:
            best_iteration = 0
            best_setup_slack = -float('inf')
            
            for i, hist in enumerate(fix_history):
                if 'hold_slack' not in hist or hist['hold_slack'] is None or hist['hold_slack'] >= 0:
                    if hist['setup_slack'] > best_setup_slack:
                        best_setup_slack = hist['setup_slack']
                        best_iteration = i
            
            if best_setup_slack == -float('inf'):
                for i, hist in enumerate(fix_history):
                    if hist['setup_slack'] > best_setup_slack:
                        best_setup_slack = hist['setup_slack']
                        best_iteration = i
            
            print(f"\n{'='*70}")
            print(f"Best results from iteration {best_iteration+1}:")
            print(f"  Setup slack: {fix_history[best_iteration]['setup_slack']} ps")
            if 'hold_slack' in fix_history[best_iteration]:
                print(f"  Hold slack: {fix_history[best_iteration]['hold_slack']} ps")
            
            # Save best design to main directory
            best_design_file = os.path.join(design_dir, f"{design_name}_best_fixed_design.v")
            write_file(best_design_file, fix_history[best_iteration]['design'])
            print(f"\nBest design saved to: {os.path.basename(best_design_file)}")
        
        # Final Summary
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"All files saved to: {design_dir}")
        print("\nGenerated files:")
        print(f"1. Verilog Analysis: {design_name}_verilog_analysis.txt")
        print(f"2. Liberty Analysis: {design_name}_liberty_analysis.txt")
        print(f"3. SDC File: {design_name}.sdc")
        print(f"4. TCL File: {design_name}.tcl")
        print(f"5. Iterations: sta_violation_fixes/ subdirectory")
        if fix_history:
            print(f"6. Best Design: {design_name}_best_fixed_design.v")
    
    else:
        print("Invalid choice. Please run the script again and select 1-5.")

if __name__ == "__main__":
    main()