#!/usr/bin/env python
"""
Standalone Runner for Employer Platform Demonstrator.
Usage:
    python demo.py
"""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    os.environ.setdefault("USE_SQLITE", "True")

    import django
    django.setup()

    from django.core.management import call_command
    call_command("migrate", verbosity=0)
    call_command("demo")
