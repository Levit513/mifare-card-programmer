#!/usr/bin/env python3
"""
MIFARE Card Programming System - Application Runner
Simple runner script to start the Flask application
"""

import os
from dotenv import load_dotenv
from app import app, db

# Load environment variables
load_dotenv()

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")
    
    # Get configuration from environment
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting MIFARE Card Programming System...")
    print(f"Access the application at: https://localhost:{port}")
    print(f"Admin login: admin / admin123")
    print(f"Note: HTTPS enabled for Web NFC API compatibility")
    
    # Enable HTTPS for Web NFC API
    app.run(host=host, port=port, debug=debug, ssl_context='adhoc')
