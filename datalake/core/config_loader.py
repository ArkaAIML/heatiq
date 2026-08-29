"""
Datalake configuration loader.
Reads sources.toml to determine how to parse external data.
"""

import tomllib
from pathlib import Path
from typing import Dict, Any, List

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.toml"

def load_sources_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Loads the sources.toml file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with config_path.open("rb") as f:
        return tomllib.load(f)

def get_infopool_sources() -> List[Dict[str, Any]]:
    """Returns a list of InfoPool source configurations sorted by priority (1 is highest)."""
    config = load_sources_config()
    infopool = config.get("infopool", {})
    source_names = infopool.get("active_sources", [])
    
    sources = []
    for name in source_names:
        src = infopool.get("sources", {}).get(name)
        if src:
            src["name"] = name
            sources.append(src)
            
    # Sort by priority ascending (priority 1 first)
    return sorted(sources, key=lambda x: x.get("priority", 999))

def get_resourcepool_sources() -> List[Dict[str, Any]]:
    """Returns a list of ResourcePool source configurations sorted by priority."""
    config = load_sources_config()
    respool = config.get("resourcepool", {})
    source_names = respool.get("active_sources", [])
    
    sources = []
    for name in source_names:
        src = respool.get("sources", {}).get(name)
        if src:
            src["name"] = name
            sources.append(src)
            
    return sorted(sources, key=lambda x: x.get("priority", 999))
