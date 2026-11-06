"""
Global configuration module for the Fire AI take-home project.
Loads environment variables from .env and defines standard file paths.
"""

import os
from pathlib import Path

# Load .env if python-dotenv is installed or fallback to os.environ
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_A_DIR = PROJECT_ROOT / "project_a"
PROJECT_B_DIR = PROJECT_ROOT / "project_b"
SHARED_DIR = PROJECT_ROOT / "shared"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_B_DIR = PROJECT_B_DIR / "data"

# Ensure reports directory exists
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_B_DIR.mkdir(parents=True, exist_ok=True)

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Operational Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
NYC_DATASET_LIMIT = int(os.getenv("NYC_DATASET_LIMIT", "10000"))

# Cost Estimation Constants (USD per 1M tokens for Gemini 1.5 Flash reference)
GEMINI_INPUT_COST_PER_M = 0.075
GEMINI_OUTPUT_COST_PER_M = 0.30
USD_TO_INR = 83.50

