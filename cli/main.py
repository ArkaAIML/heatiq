import sys
import getpass
import time
from cli.ui import (
    print_header, print_panel, print_success, 
    print_error, print_warning, print_info, print_prompt, Colors
)
from cli.client import client

def authenticate():
    """Handles the initial authentication flow."""
    print_info("Connecting to local HeatIQ backend...")
    
    if not client.check_health():
        print_error("HeatIQ backend is not running.")
        print_info("Start the HeatIQ backend and try again (e.g., python -m backend.maingate.run).")
        sys.exit(1)
        
    print_success("Backend detected")
    print_success("Main Gate reachable\n")
    
    while True:
        api_key = getpass.getpass("API Key: ").strip()
        if not api_key:
            continue
            
        # Test auth with a dummy request
        client.set_api_key(api_key)
        # We can test auth by pinging an invalid area_id and checking if we get 401/403
        success, _, err = client.process_area_id("AUTH_TEST_WARD")
        if err == "Invalid or revoked API key":
            print_error(err)
            continue
            
        print_success("API key accepted")
        print_success("Access granted\n")
        break

def format_wire1_output(data: dict) -> list:
    """Formats the Wire 1 output to dump the raw JSON string."""
    import json
    # Extract the results from the response
    results = data.get("results", [])
    
    # We want to display the raw JSON to the user for debugging purposes.
    raw_json = json.dumps(results, indent=2)
    return raw_json.split("\n")

def format_wire2_output(data: dict) -> str:
    """Formats the RecommendationOutput as a raw Markdown string."""
    rec = data.get("results", {})
    area_id = data.get("area_id", "Unknown")
    
    out = []
    out.append(f"# Ward {area_id}: Recommended Response\n")
    
    out.append("## Situation\n")
    out.append(f"{rec.get('situation_summary', 'N/A')}\n")
    
    out.append("## Priority Level\n")
    out.append(f"**{rec.get('severity', 'UNKNOWN')}**\n")
    
    out.append("## Immediate Actions\n")
    actions = rec.get("immediate_actions", [])
    if isinstance(actions, list) and actions:
        for i, act in enumerate(actions, 1):
            if isinstance(act, dict):
                name = act.get('name', 'Unknown action')
                out.append(f"{i}. **{name}**")
                
                for alloc in act.get('allocations', []):
                    out.append(f"   - {alloc}")
                
                reason = act.get('reason', '')
                if reason:
                    out.append(f"   - Reason: {reason}")
    else:
        out.append("None specified.\n")
    out.append("")
    
    out.append("## Resource Allocation\n")
    res_alloc = rec.get("resource_allocation", {})
    if isinstance(res_alloc, dict):
        if res_alloc.get("cooling_centres"):
            out.append(f"- Cooling centre: {res_alloc['cooling_centres']}")
        if res_alloc.get("healthcare_capacity"):
            out.append(f"- Healthcare capacity: {res_alloc['healthcare_capacity']}")
        if res_alloc.get("outreach_personnel"):
            out.append(f"- Outreach personnel: {res_alloc['outreach_personnel']}")
        if res_alloc.get("other"):
            out.append(f"- Other: {res_alloc['other']}")
    out.append("")
    
    out.append("## Population Priorities\n")
    pops = rec.get("population_priorities", [])
    if isinstance(pops, list) and pops:
        for i, p in enumerate(pops, 1):
            out.append(f"{i}. {p}")
    else:
        out.append("None specified.\n")
    out.append("")
    
    out.append("## Monitoring\n")
    mon = rec.get("monitoring_instructions", [])
    if isinstance(mon, list) and mon:
        for m in mon:
            out.append(f"- {m}")
    elif isinstance(mon, str) and mon:
        out.append(f"- {mon}")
    out.append("")
    
    out.append("## Why These Actions\n")
    out.append(f"{rec.get('rationale', 'N/A')}\n")
    
    out.append("## Escalation Conditions\n")
    out.append(f"{rec.get('escalation_conditions', 'N/A')}\n")
    
    return "\n".join(out)

def cmd_status():
    if client.check_health():
        print_success("Backend reachable")
    else:
        print_error("Backend unreachable")

def main_loop():
    print_info("Type 'help' for commands. Ready for next location.")
    
    while True:
        try:
            cmd = print_prompt()
            
            if not cmd:
                continue
                
            cmd_lower = cmd.lower()
            
            if cmd_lower in ('quit', 'exit'):
                break
                
            elif cmd_lower == 'help':
                print_panel("Commands", [
                    "input <place> : Process a location (e.g., 'input Bhubaneswar')",
                    "<area_id>     : Get recommendation for area (e.g., 'WARD_001')",
                    "status        : Check backend status",
                    "reconnect     : Reconnect and re-authenticate",
                    "quit / exit   : Exit CLI"
                ])
                
            elif cmd_lower == 'status':
                cmd_status()
                
            elif cmd_lower == 'reconnect':
                authenticate()
                
            elif cmd_lower.startswith('input '):
                location = cmd[6:].strip()
                print_info(f"Sending {location} to Main Gate...")
                print_info("Processing ward intelligence...")
                
                success, data, err = client.process_location(location)
                
                if success:
                    print_success("Processing complete")
                    lines = format_wire1_output(data)
                    print_panel(f"{location.upper()}", lines)
                    print_info(f"Enter area_id for recommendation (e.g., WARD_001)")
                else:
                    print_error(err)
                    
            else:
                # Assume it's an area_id
                area_id = cmd.upper()
                print_info(f"Requesting recommendation for {area_id}...")
                
                success, data, err = client.process_area_id(area_id)
                
                if success:
                    print_success("Recommendation complete\n")
                    md_output = format_wire2_output(data)
                    try:
                        from rich.console import Console
                        from rich.markdown import Markdown
                        console = Console()
                        console.print(Markdown(md_output))
                    except ImportError:
                        print(md_output)
                    print_info("Ready for next location.")
                else:
                    if err == "ward_context_not_available":
                        print_error("Recommendation unavailable.")
                        print_info("This area has not been processed by Wire 1 yet.")
                    else:
                        print_error(err)
                        
        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            print()
            break

def main():
    print_header("HeatIQ CLI\nHuman Thermal Risk Intelligence")
    authenticate()
    main_loop()

if __name__ == "__main__":
    main()
