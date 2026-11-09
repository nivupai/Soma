"""Supported Soma v0.16 SDK. Import a domain explicitly; no eager scientific imports.

Existing implementation module imports remain compatible. See SDK_API_REFERENCE.md.
"""

from soma import __version__ as __version__

__all__ = ["__version__"]
