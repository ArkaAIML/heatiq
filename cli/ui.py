import os

# Try to enable ANSI processing on Windows
if os.name == 'nt':
    os.system('color')

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def print_header(text: str):
    width = 60
    print(f"\n{Colors.CYAN}{Colors.BOLD}╔{'═' * width}╗{Colors.RESET}")
    # Center text
    centered = text.center(width)
    print(f"{Colors.CYAN}{Colors.BOLD}║{Colors.RESET}{centered}{Colors.CYAN}{Colors.BOLD}║{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}╚{'═' * width}╝{Colors.RESET}\n")

def print_panel(title: str, lines: list):
    width = 80
    print(f"\n{Colors.CYAN}╔{'═' * width}╗{Colors.RESET}")
    
    title_padded = f" {title} "
    title_line = f"║{Colors.BOLD} {title_padded.ljust(width - 2)} {Colors.RESET}{Colors.CYAN}║{Colors.RESET}"
    print(title_line)
    
    print(f"{Colors.CYAN}╠{'═' * width}╣{Colors.RESET}")
    
    for line in lines:
        if line == "---":
            # Divider
            print(f"{Colors.CYAN}╟{'─' * width}╢{Colors.RESET}")
            continue
            
        # Hard wrap if necessary, but we assume lines are reasonable length
        # Split by newline first if someone passed a multiline string
        for subline in line.split('\n'):
            # Truncate or pad
            clean_subline = subline[:width-2]
            print(f"{Colors.CYAN}║{Colors.RESET} {clean_subline.ljust(width - 2)} {Colors.CYAN}║{Colors.RESET}")
            
    print(f"{Colors.CYAN}╚{'═' * width}╝{Colors.RESET}")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.DIM}→ {text}{Colors.RESET}")

def print_prompt() -> str:
    return input(f"\n{Colors.MAGENTA}❯{Colors.RESET} ").strip()
