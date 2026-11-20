"""Validate the manifest and local asset configuration without starting a server."""

from __future__ import annotations

from src.white_label.app import create_app

if __name__ == "__main__":
    create_app()
    print("White-label manifest and assets validated.")
