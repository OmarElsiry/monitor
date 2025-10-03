#!/usr/bin/env python3
"""
🌐 Centralized Server Configuration for Nova TON Monitor
Single source of truth for all server URLs and endpoints
"""

import os
from typing import Dict, Any

class ServerConfig:
    """Centralized server configuration - modify URLs here only!"""
    
    # 🎯 MAIN SERVER CONFIGURATION - CHANGE HERE TO UPDATE EVERYWHERE
    PROTOCOL = os.getenv('SERVER_PROTOCOL', 'http')
    HOST = os.getenv('SERVER_HOST', '95.181.212.120')
    PORT = int(os.getenv('SERVER_PORT', '5001'))
    
    @classmethod
    def get_server_url(cls) -> str:
        """Get the complete server URL."""
        return f"{cls.PROTOCOL}://{cls.HOST}:{cls.PORT}"
    
    @classmethod
    def get_api_base_url(cls) -> str:
        """Get the base API URL."""
        return f"{cls.get_server_url()}/api"
    
    @classmethod
    def get_health_url(cls) -> str:
        """Get the health check URL."""
        return f"{cls.get_server_url()}/health"
    
    @classmethod
    def get_endpoint_url(cls, endpoint: str) -> str:
        """Get a specific endpoint URL."""
        endpoint = endpoint.lstrip('/')  # Remove leading slash if present
        return f"{cls.get_api_base_url()}/{endpoint}"
    
    @classmethod
    def get_all_urls(cls) -> Dict[str, str]:
        """Get all configured URLs."""
        return {
            'server_url': cls.get_server_url(),
            'api_base_url': cls.get_api_base_url(),
            'health_url': cls.get_health_url(),
            'endpoints': {
                'users_create': cls.get_endpoint_url('users/create'),
                'balance_wallet': cls.get_endpoint_url('balance/wallet'),
                'website_info': cls.get_endpoint_url('website/info'),
                'marketplace_health': cls.get_endpoint_url('marketplace/health'),
            }
        }
    
    @classmethod
    def update_server_config(cls, protocol: str = None, host: str = None, port: int = None):
        """Update server configuration at runtime."""
        if protocol:
            cls.PROTOCOL = protocol
        if host:
            cls.HOST = host
        if port:
            cls.PORT = port
    
    @classmethod
    def get_cors_origins(cls) -> list:
        """Get CORS origins including the server URL."""
        default_origins = [
            "http://localhost:3000",
            "http://localhost:3001", 
            "http://localhost:8080",
            "https://localhost:3000",
            "https://localhost:8080"
        ]
        
        # Add the server URL to CORS origins
        server_url = cls.get_server_url()
        if server_url not in default_origins:
            default_origins.append(server_url)
        
        # Add any custom origins from environment
        custom_origins = os.getenv('CORS_ORIGINS', '').split(',')
        for origin in custom_origins:
            origin = origin.strip()
            if origin and origin not in default_origins:
                default_origins.append(origin)
        
        return default_origins

# Global instance for easy importing
server_config = ServerConfig()

# Convenience functions for direct import
def get_server_url() -> str:
    """Get the server URL."""
    return server_config.get_server_url()

def get_api_base_url() -> str:
    """Get the API base URL."""
    return server_config.get_api_base_url()

def get_health_url() -> str:
    """Get the health URL."""
    return server_config.get_health_url()

def get_endpoint_url(endpoint: str) -> str:
    """Get a specific endpoint URL."""
    return server_config.get_endpoint_url(endpoint)

# Print configuration on import for debugging
if __name__ == "__main__":
    print("🌐 Nova TON Monitor - Server Configuration")
    print("=" * 50)
    urls = server_config.get_all_urls()
    print(f"Server URL: {urls['server_url']}")
    print(f"API Base URL: {urls['api_base_url']}")
    print(f"Health URL: {urls['health_url']}")
    print("\nEndpoints:")
    for name, url in urls['endpoints'].items():
        print(f"  {name}: {url}")
    print("\nCORS Origins:")
    for origin in server_config.get_cors_origins():
        print(f"  {origin}")
