import os
import sys

# Add the plugin's scripts directory to sys.path so tests can import modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
