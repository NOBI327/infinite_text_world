# ITW Development Guide

## Project
Text-based procedural MMO TRPG engine (Python/FastAPI/SQLite)

## Commands Before Commit
1. ruff check src/ tests/ - must pass
2. pytest -v - must pass

## Structure
- src/core/ - Game logic (no DB dependency)
- src/services/ - Business logic with DB
- src/db/ - ORM models
- src/api/ - FastAPI endpoints
- docs/ - Documentation

## Documentation
- WHY: docs/10_product/
- WHAT: docs/20_design/
- HOW: docs/30_technical/
- RUN: docs/40_operations/

## Rules
1. Code is truth (if implemented)
2. Ask user if unclear (if not implemented)
3. Don't guess - read docs first
