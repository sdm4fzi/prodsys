"""
This module contains the adapters for the production system which are data containers for the data models defined in `prodsys.models`. The adapters are used in all algorithms that analyze or optimize a production system. 
The data structure of the adapter can also be used to integrate new algorithms into prodsys by utilizing its defined data structure. 
The adapters is the `prodsys.models` equivalent to the `prodsys.express.ProductionSystem` class and can be created from the express object. In contrast to the adapter, the express class nests the objects in a tree structure, which makes it easier to work with when instantiating a production system, but more complicated when reviewing the data itself.
The adapter comes with a data validation that ensures that entered data is syntatically, semantically and logically valid. 
"""

from prodsys.adapters.adapter import (
    get_default_queues_for_resource,
    get_default_queue_for_sink,
    get_default_queue_for_source,
    get_production_resources,
    get_transport_resources,
    get_set_of_IDs,
    get_possible_production_processes_IDs,
    add_default_queues_to_adapter,
    check_for_clean_compound_processes,
    ProductionSystemAdapter,
)
from prodsys.adapters.json_adapter import JsonProductionSystemAdapter
