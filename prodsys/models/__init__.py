"""
The `prodsys.models` package contains the data structures to describe a production system's structure and its performance. These data structures are utilized in prodsys to have a common format for all algorithms in simulation, optimization, analysis and the prodsys webserver.
All of these formats are compatible with the `prodsys.express` API. However, the conversion works only in one direction: from `prodsys.express` to `prodsys.models`. 

The following modules are available:

- `prodsys.models.core_asset`: Contains the abstract base class for data objects.
- `prodsys.models.product_data`: Contains classes to represent products.
- `prodsys.models.performance_data`: Contains classes to represent performance data.
- `prodsys.models.performance_indicators`: Contains classes to represent performance indicators (KPIs).
- `prodsys.models.processes_data`: Contains classes to represent processes.
- `prodsys.models.queue_data`: Contains classes to represent queues.
- `prodsys.models.resource_data`: Contains classes to represent resources.
- `prodsys.models.node_data`: Contains classes to represent nodes in a link.
- `prodsys.models.scenario_data`: Contains classes to represent scenario data.
- `prodsys.models.sink_data`: Contains classes to represent sinks.
- `prodsys.models.source_data`: Contains classes to represent sources.
- `prodsys.models.state_data`: Contains classes to represent states.
- `prodsys.models.links_data`: Contains classes to represent links.
- `prodsys.models.time_model_data`: Contains classes to represent time models.
"""