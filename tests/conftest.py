"""Pytest configuration and shared fixtures.

Provides common fixtures and configuration for all test modules.
"""

import sys
from sqlalchemy import JSON

# Patch JSONB before any models are imported
from sqlalchemy.dialects import postgresql
postgresql.JSONB = JSON

import pytest
