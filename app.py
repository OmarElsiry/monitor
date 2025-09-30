#!/usr/bin/env python3
"""
WSGI Application Entry Point for Railway Deployment
"""

from api.production_server import create_production_server

# Create the Flask application instance
server = create_production_server()
app = server.app

# This makes the module importable by Gunicorn
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=False)
