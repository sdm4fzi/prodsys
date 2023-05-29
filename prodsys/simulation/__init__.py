"""
This package contains the simulation module. It is based on the SimPy package and uses the `prodsys.models` API for running the simulation. Objects are created with the `prodsys.factories`.

The simulation module contains the following modules:

- `prodsys.simulation.control`: Contains the logic for controlling the processes of resources in the simulation.
- `prodsys.simulation.logger`: Used for logging events in the simulation for later analysis.
- `prodsys.simulation.observer`: Can be used to observe the simulation and its processes while simulation.
- `prodsys.simulation.process_models`: Contains process models for products for the simulation.
- `prodsys.simulation.process`: All processes used in the simulation for product processing or transport.
- `prodsys.simulation.product`: Contains the logic for the product object in the simulation.
- `prodsys.simulation.request`: Has classes for representing requests of products to resources for processing or transport.
- `prodsys.simulation.resources`: Contains the logic for all resources in the simulation.
- `prodsys.simulation.router`: Contains the logic for routing products in the simulation.
- `prodsys.simulation.sim`: Simulation class for running the simulation.
- `prodsys.simulation.sink`: Contains the logic for sinks in the simulation.
- `prodsys.simulation.source`: Contains the logic for sources in the simulation.
- `prodsys.simulation.state`: Contains the logic for the state of resources in the simulation.
- `prodsys.simulation.store`: Contains the logic for product queues of resources in the simulation.
- `prodsys.simulation.time_model`: Contains the logic for time models in the simulation.


"""