"""
Adapter module for prodsys.

This module provides aliases and utility functions for working with production system data.
It serves as a compatibility layer and provides convenient access to production system functionality.
"""

from prodsys.models.production_system_data import (
    ProductionSystemData,
    get_production_resources,
    get_transport_resources,
    check_for_clean_compound_processes,
    get_missing_production_processes,
    get_missing_transport_processes,
    get_missing_capability_processes,
    get_required_process_ids,
    get_available_process_ids,
    get_required_production_processes,
    get_required_transport_processes,
    get_required_capability_processes,
    get_available_production_processes,
    get_available_transport_processes,
    get_available_capability_processes,
)

# Re-export the main ProductionSystemData class as the primary adapter
__all__ = [
    "ProductionSystemData",
    "get_production_resources", 
    "get_transport_resources",
    "check_for_clean_compound_processes",
    "get_missing_production_processes",
    "get_missing_transport_processes",
    "get_missing_capability_processes",
    "get_required_process_ids",
    "get_available_process_ids",
    "get_required_production_processes",
    "get_required_transport_processes",
    "get_required_capability_processes",
    "get_available_production_processes",
    "get_available_transport_processes",
    "get_available_capability_processes",
]
