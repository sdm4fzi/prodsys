"""
The `prodsys.data_structures` package contains the data structures to describe a production system's structure and its performance. These data structures are utilized in prodsys to have a common format for all algorithms in simulation, optimization, analysis and the prodsys webserver.
All of these formats are compatible with the `prodsys.express` API. However, the conversion works only in one direction: from `prodsys.express` to `prodsys.data_structures`. 

The following modules are available:

- `prodsys.data_structures.core_asset`: Contains the abstract base class for data objects.
- `prodsys.data_structures.product_data`: Contains classes to represent products.
- `prodsys.data_structures.performance_data`: Contains classes to represent performance data.
- `prodsys.data_structures.performance_indicators`: Contains classes to represent performance indicators (KPIs).
- `prodsys.data_structures.processes_data`: Contains classes to represent processes.
- `prodsys.data_structures.queue_data`: Contains classes to represent queues.
- `prodsys.data_structures.resource_data`: Contains classes to represent resources.
- `prodsys.data_structures.scenario_data`: Contains classes to represent scenario data.
- `prodsys.data_structures.sink_data`: Contains classes to represent sinks.
- `prodsys.data_structures.source_data`: Contains classes to represent sources.
- `prodsys.data_structures.state_data`: Contains classes to represent states.
- `prodsys.data_structures.time_model_data`: Contains classes to represent time models.
"""