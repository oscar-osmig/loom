#!/usr/bin/env python3
"""
Loom - A symbolic knowledge system that weaves connections like neural threads.

Run with: python main.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from web_app import app


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', '') == '1')
