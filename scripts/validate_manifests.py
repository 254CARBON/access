#!/usr/bin/env python3
"""
Service manifest validation script for 254Carbon Access Layer.
This script validates all service-manifest.yaml files for correctness.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List

def validate_manifest(manifest_path: Path) -> List[str]:
    """Validate a single service manifest file."""
    errors = []
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML: {e}")
        return errors
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return errors
    
    # Required fields
    required_fields = [
        'service_name', 'domain', 'runtime', 'language_version',
        'api_contracts', 'dependencies', 'maturity', 'sla', 'owner'
    ]
    
    for field in required_fields:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
    
    # Validate service_name
    if 'service_name' in manifest:
        service_name = manifest['service_name']
        if not isinstance(service_name, str) or not service_name:
            errors.append("service_name must be a non-empty string")
    
    # Validate domain
    if 'domain' in manifest:
        domain = manifest['domain']
        if domain != 'access':
            errors.append("domain must be 'access'")
    
    # Validate runtime
    if 'runtime' in manifest:
        runtime = manifest['runtime']
        if runtime != 'python':
            errors.append("runtime must be 'python'")
    
    # Validate language_version
    if 'language_version' in manifest:
        lang_version = manifest['language_version']
        if lang_version != "3.12":
            errors.append("language_version must be '3.12'")
    
    # Validate api_contracts
    if 'api_contracts' in manifest:
        contracts = manifest['api_contracts']
        if not isinstance(contracts, list) or not contracts:
            errors.append("api_contracts must be a non-empty list")
        else:
            for contract in contracts:
                if not isinstance(contract, str) or '@' not in contract:
                    errors.append(f"Invalid contract format: {contract}")
    
    # Validate dependencies
    if 'dependencies' in manifest:
        deps = manifest['dependencies']
        if not isinstance(deps, dict):
            errors.append("dependencies must be a dictionary")
        else:
            for dep_type in ['internal', 'external']:
                if dep_type not in deps:
                    errors.append(f"Missing dependency type: {dep_type}")
                elif not isinstance(deps[dep_type], list):
                    errors.append(f"{dep_type} dependencies must be a list")
    
    # Validate maturity
    if 'maturity' in manifest:
        maturity = manifest['maturity']
        valid_maturities = ['stable', 'beta', 'alpha', 'experimental']
        if maturity not in valid_maturities:
            errors.append(f"maturity must be one of: {valid_maturities}")
    
    # Validate SLA
    if 'sla' in manifest:
        sla = manifest['sla']
        if not isinstance(sla, dict):
            errors.append("sla must be a dictionary")
        else:
            if 'p95_latency_ms' not in sla:
                errors.append("sla must include p95_latency_ms")
            if 'availability' not in sla:
                errors.append("sla must include availability")
    
    # Validate owner
    if 'owner' in manifest:
        owner = manifest['owner']
        if owner != 'platform':
            errors.append("owner must be 'platform'")
    
    return errors

def main():
    """Main function to validate all service manifests."""
    print("Validating service manifests...")
    
    # Find all service directories
    service_dirs = [d for d in Path('.').iterdir() if d.is_dir() and d.name.startswith('service-')]
    
    if not service_dirs:
        print("No service directories found")
        return 1
    
    total_errors = 0
    
    for service_dir in sorted(service_dirs):
        manifest_path = service_dir / 'service-manifest.yaml'
        
        if not manifest_path.exists():
            print(f"❌ {service_dir.name}: service-manifest.yaml not found")
            total_errors += 1
            continue
        
        errors = validate_manifest(manifest_path)
        
        if errors:
            print(f"❌ {service_dir.name}: {len(errors)} validation errors")
            for error in errors:
                print(f"   - {error}")
            total_errors += len(errors)
        else:
            print(f"✅ {service_dir.name}: manifest is valid")
    
    print(f"\nValidation complete: {total_errors} total errors")
    
    if total_errors == 0:
        print("All service manifests are valid!")
        return 0
    else:
        print("Some service manifests have validation errors")
        return 1

if __name__ == "__main__":
    sys.exit(main())
