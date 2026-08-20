"""Workspace-safe repository tools used by the Phase 2 runtime.

Submodules are intentionally not imported here.  The core model package imports
the contracts during startup, so eager re-exports would create a storage/model
cycle.
"""
