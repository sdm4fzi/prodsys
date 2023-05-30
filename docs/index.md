# Welcome to prodsys

This is the documentation for the prodsys package, a package for modeling, simulating, and optimizing production systems based on the product, process and resource (PPR) modelling principle.

## Installation

To install the package, run the following command in the terminal:

```bash
pip install prodsys
```

Please note that the package is only compatible with Python 3.11 or higher.

## Getting started

The package is designed to be easy to use. The following example shows how to model a simple production system and simulate it. The production system contains a single milling machine that performs milling processes on aluminium housings. The transport is thereby performed by a worker.  At first, just import the express API of `prodsys`:

```python
import prodsys.express as psx
```

We now create all components required for describing the production system. At first we define times for all arrival, production and transport processes:

```python
milling_time = psx.FunctionTimeModel(distribution_function="normal", location=1, scale=0.1, ID="milling_time")
transport_time = psx.FunctionTimeModel(distribution_function="normal", location=0.3, scale=0.2, ID="transport_time")
arrival_time_of_housings = psx.FunctionTimeModel(distribution_function="exponential", location=1.5, ID="arrival_time_of_housings")
```

Next, we can define the production and transport process in the system by using the created time models:

```python
milling_process = psx.ProductionProcess(milling_time, ID="milling_process")
transport_process = psx.TransportProcess(transport_time, ID="transport_process")
```

With the processes defined, we can now create the production and transport resources:

```python
milling_machine = psx.ProductionResource([milling_process], location=[5, 5], ID="milling_machine")
worker = psx.TransportResource([transport_process], location=[0, 0], ID="worker")
```

Now we define our product, the housing, that is produced in the system. For this example it requires only a single processsing step:

```python
housing = psx.Product([milling_process], transport_process, ID="housing")
```

Only the sources and sinks that are responsible for creating the housing and storing finished housing are misssing:

```py
source = psx.Source(housing, arrival_time_of_housings, location=[0, 0], ID="source")
sink = psx.Sink(housing, location=[20, 20], ID="sink")
```

Finally, we can create our production system, run the simulation for 60 minutes and print aggregated simulation results:

```python
production_system = psx.ProductionSystem([milling_machine, worker], [source], [sink])
production_system.run(60)
production_system.runner.print_results()
```

As we can see, the system produced 39 parts in this hour with an work in progress (WIP ~ number of products in the system) of 4.125 and utilized the milling machine with 79.69% and the worker for 78.57%.

Note, that this example only covers the most basic functionalities of `prodsys`. For more elaborate guides that cover more of the package's features, please see the [tutorials](Tutorials/tutorial_0_overview.md). For a complete overview of the package's functionality, please see the [API reference](API_reference/API_reference_0_overview.md).

## Contributing

`prodsys` is a new project and has therefore much room for improvement. Therefore, it would be a pleasure to get feedback or support! If you want to contribute to the package, either create issues on [prodsys' github page](https://github.com/sdm4fzi/prodsys) for discussing new features or contact me directly via [github](https://github.com/SebBehrendt) or [email](mailto:sebastian.behrendt@kit.edu).

## License

The package is licensed under the [MIT license](LICENSE).

## Acknowledgements

We extend our sincere thanks to the German Federal Ministry for Economic Affairs and Climate Action
(BMWK) for supporting this research project 13IK001ZF “Software-Defined Manufacturing for the
automotive and supplying industry  [https://www.sdm4fzi.de/](https://www.sdm4fzi.de/)”.
