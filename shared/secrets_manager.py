"""
Secrets management for the access layer services.
"""

import os
import json
import base64
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Manages secrets for the access layer services.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize the secrets manager.
        
        Args:
            master_key: Master key for encryption/decryption
        """
        self.master_key = master_key or os.getenv("ACCESS_MASTER_KEY")
        if not self.master_key:
            raise ValueError("Master key is required")
        
        self._fernet = self._create_fernet()
    
    def _create_fernet(self) -> Fernet:
        """
        Create a Fernet cipher instance.
        
        Returns:
            Fernet cipher instance
        """
        # Derive key from master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'access_layer_salt',  # In production, use a random salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def encrypt_secret(self, secret: str) -> str:
        """
        Encrypt a secret.
        
        Args:
            secret: Secret to encrypt
            
        Returns:
            Encrypted secret
        """
        try:
            encrypted = self._fernet.encrypt(secret.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            raise
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt a secret.
        
        Args:
            encrypted_secret: Encrypted secret
            
        Returns:
            Decrypted secret
        """
        try:
            decoded = base64.urlsafe_b64decode(encrypted_secret.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            raise
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret by key.
        
        Args:
            key: Secret key
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        # Try environment variable first
        env_key = f"ACCESS_{key.upper()}"
        secret = os.getenv(env_key)
        
        if secret:
            return secret
        
        # Try encrypted secret file
        secret_file = os.getenv("ACCESS_SECRETS_FILE")
        if secret_file and os.path.exists(secret_file):
            try:
                with open(secret_file, 'r') as f:
                    secrets = json.load(f)
                
                if key in secrets:
                    encrypted_secret = secrets[key]
                    return self.decrypt_secret(encrypted_secret)
            except Exception as e:
                logger.warning(f"Failed to read secrets file: {e}")
        
        return default
    
    def set_secret(self, key: str, value: str, encrypt: bool = True) -> None:
        """
        Set a secret.
        
        Args:
            key: Secret key
            value: Secret value
            encrypt: Whether to encrypt the secret
        """
        if encrypt:
            encrypted_value = self.encrypt_secret(value)
        else:
            encrypted_value = value
        
        # Write to secrets file
        secret_file = os.getenv("ACCESS_SECRETS_FILE", "secrets.json")
        secrets = {}
        
        if os.path.exists(secret_file):
            try:
                with open(secret_file, 'r') as f:
                    secrets = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read existing secrets file: {e}")
        
        secrets[key] = encrypted_value
        
        try:
            with open(secret_file, 'w') as f:
                json.dump(secrets, f, indent=2)
            logger.info(f"Secret '{key}' saved to {secret_file}")
        except Exception as e:
            logger.error(f"Failed to save secret: {e}")
            raise
    
    def get_database_credentials(self) -> Dict[str, str]:
        """
        Get database credentials.
        
        Returns:
            Dictionary with database credentials
        """
        return {
            "host": self.get_secret("DB_HOST", "localhost"),
            "port": self.get_secret("DB_PORT", "5432"),
            "database": self.get_secret("DB_NAME", "access_layer"),
            "username": self.get_secret("DB_USER", "postgres"),
            "password": self.get_secret("DB_PASSWORD", "postgres"),
        }
    
    def get_redis_credentials(self) -> Dict[str, str]:
        """
        Get Redis credentials.
        
        Returns:
            Dictionary with Redis credentials
        """
        return {
            "host": self.get_secret("REDIS_HOST", "localhost"),
            "port": self.get_secret("REDIS_PORT", "6379"),
            "password": self.get_secret("REDIS_PASSWORD"),
            "db": self.get_secret("REDIS_DB", "0"),
        }
    
    def get_kafka_credentials(self) -> Dict[str, str]:
        """
        Get Kafka credentials.
        
        Returns:
            Dictionary with Kafka credentials
        """
        return {
            "bootstrap_servers": self.get_secret("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            "security_protocol": self.get_secret("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            "sasl_mechanism": self.get_secret("KAFKA_SASL_MECHANISM"),
            "sasl_username": self.get_secret("KAFKA_SASL_USERNAME"),
            "sasl_password": self.get_secret("KAFKA_SASL_PASSWORD"),
        }
    
    def get_keycloak_credentials(self) -> Dict[str, str]:
        """
        Get Keycloak credentials.
        
        Returns:
            Dictionary with Keycloak credentials
        """
        return {
            "base_url": self.get_secret("KEYCLOAK_BASE_URL", "http://localhost:8080"),
            "realm": self.get_secret("KEYCLOAK_REALM", "254carbon"),
            "client_id": self.get_secret("KEYCLOAK_CLIENT_ID", "access-layer"),
            "client_secret": self.get_secret("KEYCLOAK_CLIENT_SECRET"),
            "admin_username": self.get_secret("KEYCLOAK_ADMIN_USERNAME", "admin"),
            "admin_password": self.get_secret("KEYCLOAK_ADMIN_PASSWORD"),
        }
    
    def get_jwt_secrets(self) -> Dict[str, str]:
        """
        Get JWT secrets.
        
        Returns:
            Dictionary with JWT secrets
        """
        return {
            "secret_key": self.get_secret("JWT_SECRET_KEY"),
            "algorithm": self.get_secret("JWT_ALGORITHM", "HS256"),
            "access_token_expire_minutes": self.get_secret("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"),
            "refresh_token_expire_days": self.get_secret("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"),
        }
    
    def get_api_keys(self) -> Dict[str, str]:
        """
        Get API keys.
        
        Returns:
            Dictionary with API keys
        """
        return {
            "admin_key": self.get_secret("API_ADMIN_KEY"),
            "service_key": self.get_secret("API_SERVICE_KEY"),
            "readonly_key": self.get_secret("API_READONLY_KEY"),
        }
    
    def get_monitoring_credentials(self) -> Dict[str, str]:
        """
        Get monitoring credentials.
        
        Returns:
            Dictionary with monitoring credentials
        """
        return {
            "prometheus_url": self.get_secret("PROMETHEUS_URL", "http://localhost:9090"),
            "grafana_url": self.get_secret("GRAFANA_URL", "http://localhost:3000"),
            "grafana_admin_password": self.get_secret("GRAFANA_ADMIN_PASSWORD"),
            "jaeger_url": self.get_secret("JAEGER_URL", "http://localhost:16686"),
        }
    
    def validate_secrets(self) -> bool:
        """
        Validate that all required secrets are present.
        
        Returns:
            True if all secrets are valid, False otherwise
        """
        required_secrets = [
            "DB_PASSWORD",
            "REDIS_PASSWORD",
            "JWT_SECRET_KEY",
            "API_ADMIN_KEY",
        ]
        
        missing_secrets = []
        for secret in required_secrets:
            if not self.get_secret(secret):
                missing_secrets.append(secret)
        
        if missing_secrets:
            logger.error(f"Missing required secrets: {missing_secrets}")
            return False
        
        return True
    
    def rotate_secret(self, key: str, new_value: str) -> None:
        """
        Rotate a secret.
        
        Args:
            key: Secret key
            new_value: New secret value
        """
        old_value = self.get_secret(key)
        if old_value:
            logger.info(f"Rotating secret '{key}'")
        
        self.set_secret(key, new_value)
        logger.info(f"Secret '{key}' rotated successfully")
    
    def list_secrets(self) -> Dict[str, bool]:
        """
        List all available secrets.
        
        Returns:
            Dictionary mapping secret keys to availability status
        """
        secrets = {}
        
        # Check environment variables
        for key, value in os.environ.items():
            if key.startswith("ACCESS_"):
                secret_key = key[7:].lower()  # Remove "ACCESS_" prefix
                secrets[secret_key] = True
        
        # Check secrets file
        secret_file = os.getenv("ACCESS_SECRETS_FILE")
        if secret_file and os.path.exists(secret_file):
            try:
                with open(secret_file, 'r') as f:
                    file_secrets = json.load(f)
                
                for key in file_secrets.keys():
                    secrets[key] = True
            except Exception as e:
                logger.warning(f"Failed to read secrets file: {e}")
        
        return secrets


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """
    Get the global secrets manager instance.
    
    Returns:
        SecretsManager instance
    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def init_secrets_manager(master_key: Optional[str] = None) -> SecretsManager:
    """
    Initialize the global secrets manager.
    
    Args:
        master_key: Master key for encryption/decryption
        
    Returns:
        SecretsManager instance
    """
    global _secrets_manager
    _secrets_manager = SecretsManager(master_key)
    return _secrets_manager
