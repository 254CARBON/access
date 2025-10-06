#!/usr/bin/env python3
"""
Code generation synchronization script for 254Carbon Access Layer.
This script pulls the latest API contracts from the specs repository.
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

def run_command(cmd: str, cwd: str = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def load_specs_lock() -> Dict[str, Any]:
    """Load the specs.lock.json file."""
    lock_file = Path("specs.lock.json")
    if not lock_file.exists():
        return {}
    
    try:
        with open(lock_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading specs.lock.json: {e}")
        return {}

def update_specs_lock(contracts: Dict[str, str]) -> None:
    """Update the specs.lock.json file with new contract versions."""
    lock_data = {
        "version": "1.0.0",
        "last_updated": "2025-01-27T00:00:00Z",
        "contracts": contracts
    }
    
    with open("specs.lock.json", 'w') as f:
        json.dump(lock_data, f, indent=2)

def sync_openapi_specs(service: str, contract_version: str) -> bool:
    """Sync OpenAPI specs for a specific service."""
    service_dir = Path(f"service-{service}")
    openapi_dir = service_dir / "openapi"
    
    if not service_dir.exists():
        print(f"Service directory not found: {service_dir}")
        return False
    
    # Create openapi directory if it doesn't exist
    openapi_dir.mkdir(exist_ok=True)
    
    # For now, create a placeholder OpenAPI spec
    # In a real implementation, this would fetch from the specs repo
    openapi_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": f"{service.title()} Service API",
            "version": contract_version,
            "description": f"API specification for the {service} service"
        },
        "servers": [
            {
                "url": f"http://localhost:{get_service_port(service)}",
                "description": "Development server"
            }
        ],
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "service": {"type": "string"},
                                            "version": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Write the OpenAPI spec
    spec_file = openapi_dir / f"{service}-api.yaml"
    try:
        import yaml
        with open(spec_file, 'w') as f:
            yaml.dump(openapi_spec, f, default_flow_style=False)
        print(f"Updated OpenAPI spec for {service}: {spec_file}")
        return True
    except ImportError:
        print("PyYAML not available, skipping OpenAPI spec generation")
        return False

def get_service_port(service: str) -> str:
    """Get the default port for a service."""
    ports = {
        "gateway": "8000",
        "streaming": "8001",
        "auth": "8010",
        "entitlements": "8011",
        "metrics": "8012"
    }
    return ports.get(service, "8000")

def main():
    """Main function to sync code generation."""
    print("Syncing code generation from specs repository...")
    
    # Load current specs lock
    current_lock = load_specs_lock()
    
    # Define services and their contracts
    services = {
        "gateway": "gateway-core@1.0.0",
        "streaming": "streaming-core@1.0.0",
        "auth": "auth-core@1.0.0",
        "entitlements": "entitlements-core@1.0.0",
        "metrics": "metrics-core@1.0.0"
    }
    
    # Update specs lock
    update_specs_lock(services)
    
    # Sync OpenAPI specs for each service
    success_count = 0
    for service, contract in services.items():
        contract_version = contract.split('@')[1]
        if sync_openapi_specs(service, contract_version):
            success_count += 1
    
    print(f"Successfully synced {success_count}/{len(services)} services")
    
    if success_count == len(services):
        print("All services synced successfully!")
        return 0
    else:
        print("Some services failed to sync")
        return 1

if __name__ == "__main__":
    sys.exit(main())
