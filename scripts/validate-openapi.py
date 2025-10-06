#!/usr/bin/env python3
"""
OpenAPI specification validation script for 254Carbon Access Layer.
This script validates OpenAPI specifications for all services.
"""

import os
import sys
import yaml
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from jsonschema import validate, ValidationError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class OpenAPIValidator:
    """OpenAPI specification validator."""
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.services = ["gateway", "streaming", "auth", "entitlements", "metrics"]
        self.errors = []
        self.warnings = []
    
    def validate_spec_file(self, spec_path: Path) -> bool:
        """
        Validate a single OpenAPI specification file.
        
        Args:
            spec_path: Path to the OpenAPI specification file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            with open(spec_path, 'r') as f:
                spec = yaml.safe_load(f)
            
            # Basic structure validation
            if not self._validate_basic_structure(spec, spec_path):
                return False
            
            # OpenAPI version validation
            if not self._validate_openapi_version(spec, spec_path):
                return False
            
            # Info section validation
            if not self._validate_info_section(spec, spec_path):
                return False
            
            # Paths validation
            if not self._validate_paths(spec, spec_path):
                return False
            
            # Components validation
            if not self._validate_components(spec, spec_path):
                return False
            
            # Security validation
            if not self._validate_security(spec, spec_path):
                return False
            
            logger.info(f"✅ {spec_path.name} is valid")
            return True
            
        except Exception as e:
            self.errors.append(f"Error validating {spec_path}: {e}")
            logger.error(f"❌ Error validating {spec_path}: {e}")
            return False
    
    def _validate_basic_structure(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate basic OpenAPI structure."""
        required_fields = ["openapi", "info", "paths"]
        
        for field in required_fields:
            if field not in spec:
                self.errors.append(f"{spec_path.name}: Missing required field '{field}'")
                return False
        
        return True
    
    def _validate_openapi_version(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate OpenAPI version."""
        openapi_version = spec.get("openapi", "")
        
        if not openapi_version.startswith("3."):
            self.errors.append(f"{spec_path.name}: Invalid OpenAPI version '{openapi_version}'. Must be 3.x")
            return False
        
        return True
    
    def _validate_info_section(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate info section."""
        info = spec.get("info", {})
        required_info_fields = ["title", "version"]
        
        for field in required_info_fields:
            if field not in info:
                self.errors.append(f"{spec_path.name}: Missing info.{field}")
                return False
        
        # Validate version format (semantic versioning)
        version = info.get("version", "")
        if not self._is_semantic_version(version):
            self.warnings.append(f"{spec_path.name}: Version '{version}' is not semantic versioning format")
        
        return True
    
    def _validate_paths(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate paths section."""
        paths = spec.get("paths", {})
        
        if not paths:
            self.errors.append(f"{spec_path.name}: No paths defined")
            return False
        
        for path, path_item in paths.items():
            if not self._validate_path_item(path, path_item, spec_path):
                return False
        
        return True
    
    def _validate_path_item(self, path: str, path_item: Dict[str, Any], spec_path: Path) -> bool:
        """Validate a single path item."""
        # Validate path format
        if not path.startswith("/"):
            self.errors.append(f"{spec_path.name}: Path '{path}' must start with '/'")
            return False
        
        # Validate HTTP methods
        valid_methods = ["get", "post", "put", "delete", "patch", "head", "options", "trace"]
        
        for method, operation in path_item.items():
            if method.lower() in valid_methods:
                if not self._validate_operation(method, operation, spec_path):
                    return False
        
        return True
    
    def _validate_operation(self, method: str, operation: Dict[str, Any], spec_path: Path) -> bool:
        """Validate a single operation."""
        # Check for required fields
        if "responses" not in operation:
            self.errors.append(f"{spec_path.name}: Operation {method.upper()} missing 'responses'")
            return False
        
        # Validate responses
        responses = operation.get("responses", {})
        if not responses:
            self.errors.append(f"{spec_path.name}: Operation {method.upper()} has no responses")
            return False
        
        # Check for at least one successful response
        success_responses = [code for code in responses.keys() if code.startswith("2")]
        if not success_responses:
            self.warnings.append(f"{spec_path.name}: Operation {method.upper()} has no 2xx responses")
        
        # Validate request body for POST/PUT/PATCH
        if method.lower() in ["post", "put", "patch"]:
            if "requestBody" not in operation:
                self.warnings.append(f"{spec_path.name}: Operation {method.upper()} missing 'requestBody'")
        
        return True
    
    def _validate_components(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate components section."""
        components = spec.get("components", {})
        
        # Validate schemas
        schemas = components.get("schemas", {})
        for schema_name, schema in schemas.items():
            if not self._validate_schema(schema_name, schema, spec_path):
                return False
        
        # Validate security schemes
        security_schemes = components.get("securitySchemes", {})
        for scheme_name, scheme in security_schemes.items():
            if not self._validate_security_scheme(scheme_name, scheme, spec_path):
                return False
        
        return True
    
    def _validate_schema(self, schema_name: str, schema: Dict[str, Any], spec_path: Path) -> bool:
        """Validate a schema definition."""
        # Basic schema validation
        if "type" not in schema:
            self.warnings.append(f"{spec_path.name}: Schema '{schema_name}' missing 'type'")
        
        return True
    
    def _validate_security_scheme(self, scheme_name: str, scheme: Dict[str, Any], spec_path: Path) -> bool:
        """Validate a security scheme definition."""
        if "type" not in scheme:
            self.errors.append(f"{spec_path.name}: Security scheme '{scheme_name}' missing 'type'")
            return False
        
        return True
    
    def _validate_security(self, spec: Dict[str, Any], spec_path: Path) -> bool:
        """Validate security section."""
        security = spec.get("security", [])
        
        # Check if security is defined at global level
        if not security:
            self.warnings.append(f"{spec_path.name}: No global security defined")
        
        return True
    
    def _is_semantic_version(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        import re
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'
        return bool(re.match(pattern, version))
    
    def validate_all_specs(self) -> bool:
        """Validate all OpenAPI specifications."""
        logger.info("Validating OpenAPI specifications...")
        
        all_valid = True
        
        for service in self.services:
            spec_path = self.base_path / f"service_{service}" / "openapi" / f"{service}-api.yaml"
            
            if not spec_path.exists():
                self.errors.append(f"OpenAPI spec not found: {spec_path}")
                all_valid = False
                continue
            
            if not self.validate_spec_file(spec_path):
                all_valid = False
        
        return all_valid
    
    def validate_consistency(self) -> bool:
        """Validate consistency across all specifications."""
        logger.info("Validating consistency across specifications...")
        
        # Check version consistency
        versions = {}
        for service in self.services:
            spec_path = self.base_path / f"service_{service}" / "openapi" / f"{service}-api.yaml"
            
            if spec_path.exists():
                try:
                    with open(spec_path, 'r') as f:
                        spec = yaml.safe_load(f)
                    versions[service] = spec.get("info", {}).get("version", "unknown")
                except Exception as e:
                    self.errors.append(f"Error reading {spec_path}: {e}")
                    return False
        
        # Check if all services use the same version
        unique_versions = set(versions.values())
        if len(unique_versions) > 1:
            self.warnings.append(f"Services have different API versions: {versions}")
        
        return True
    
    def generate_documentation(self, output_dir: str = "docs") -> bool:
        """Generate documentation from OpenAPI specifications."""
        logger.info("Generating documentation...")
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        for service in self.services:
            spec_path = self.base_path / f"service_{service}" / "openapi" / f"{service}-api.yaml"
            
            if not spec_path.exists():
                continue
            
            try:
                with open(spec_path, 'r') as f:
                    spec = yaml.safe_load(f)
                
                # Generate HTML documentation
                html_path = output_path / f"{service}-api.html"
                self._generate_html_docs(spec, html_path)
                
                # Generate JSON specification
                json_path = output_path / f"{service}-api.json"
                with open(json_path, 'w') as f:
                    json.dump(spec, f, indent=2)
                
                logger.info(f"Generated documentation for {service}")
                
            except Exception as e:
                self.errors.append(f"Error generating documentation for {service}: {e}")
                return False
        
        return True
    
    def _generate_html_docs(self, spec: Dict[str, Any], output_path: Path) -> None:
        """Generate HTML documentation from OpenAPI spec."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{spec.get('info', {}).get('title', 'API Documentation')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; }}
        .endpoint {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .method {{ font-weight: bold; color: #007bff; }}
        .path {{ font-family: monospace; }}
        .description {{ margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{spec.get('info', {}).get('title', 'API Documentation')}</h1>
        <p>{spec.get('info', {}).get('description', '')}</p>
        <p>Version: {spec.get('info', {}).get('version', '')}</p>
    </div>
    
    <h2>Endpoints</h2>
"""
        
        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    html_content += f"""
    <div class="endpoint">
        <div class="method">{method.upper()}</div>
        <div class="path">{path}</div>
        <div class="description">{operation.get('summary', '')}</div>
        <p>{operation.get('description', '')}</p>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html_content)
    
    def print_results(self) -> None:
        """Print validation results."""
        if self.errors:
            logger.error("Validation errors:")
            for error in self.errors:
                logger.error(f"  ❌ {error}")
        
        if self.warnings:
            logger.warning("Validation warnings:")
            for warning in self.warnings:
                logger.warning(f"  ⚠️  {warning}")
        
        if not self.errors and not self.warnings:
            logger.info("✅ All OpenAPI specifications are valid!")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate OpenAPI specifications")
    parser.add_argument("--base-path", default=".", help="Base path for OpenAPI specs")
    parser.add_argument("--generate-docs", action="store_true", help="Generate documentation")
    parser.add_argument("--output-dir", default="docs", help="Output directory for documentation")
    parser.add_argument("--service", help="Validate specific service only")
    
    args = parser.parse_args()
    
    validator = OpenAPIValidator(args.base_path)
    
    if args.service:
        # Validate specific service
        spec_path = Path(args.base_path) / f"service_{args.service}" / "openapi" / f"{args.service}-api.yaml"
        if not spec_path.exists():
            logger.error(f"OpenAPI spec not found: {spec_path}")
            sys.exit(1)
        
        if not validator.validate_spec_file(spec_path):
            sys.exit(1)
    else:
        # Validate all services
        if not validator.validate_all_specs():
            sys.exit(1)
        
        # Validate consistency
        validator.validate_consistency()
    
    # Generate documentation if requested
    if args.generate_docs:
        validator.generate_documentation(args.output_dir)
    
    # Print results
    validator.print_results()
    
    # Exit with error code if there are errors
    if validator.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
