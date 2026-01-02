![prodsys logo](https://raw.githubusercontent.com/sdm4fzi/prodsys/main/resources/logo.svg)

*prodsys - modeling, simulating and optimizing production systems*

![Build-sucess](https://img.shields.io/badge/build-success-green)
![PyPI](https://img.shields.io/pypi/v/prodsys)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/prodsys)
![Docu](https://img.shields.io/badge/docu-full-green)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10995273.svg)](https://doi.org/10.5281/zenodo.10995273)

prodsys is a python package for modeling, simulating and optimizing production systems based on the product, process and resource (PPR) modelling principle. 

## Installation

To install the package, run one of the following commands in the terminal:

Using `pip`:
```bash
pip install prodsys
```

Using `uv`:
```bash
uv pip install prodsys
```

Please note that prodsys is currently only fully compatible with Python 3.11. Other versions might cause some errors.

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
worker = psx.Resource([transport_process], location=[0, 0], ID="worker")
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

As we can see, the system produced 39 parts in this hour with an work in progress (WIP ~ number of products in the system) of 4.125 and utilized the milling machine with 79.69% and the worker for 78.57% at the PR percentage, the rest of the time, both resource are in standby (SB). Note that these results stay the same although there are stochastic processes in the simulation. This is caused by seeding the random number generator with a fixed value. If you want to get different results, just specify another value for `seed` parameter from the `run` method.

``` python
production_system.run(60, seed=1)
production_system.runner.print_results()
```

As expected, the performance of the production system changed quite strongly with the new parameters. The system now produces 26 parts in this hour with an work in progress (WIP ~ number of products in the system) of 1.68. As the arrival process of the housing is modelled by an exponential distribution and we only consider 60 minutes of simulation, this is absolutely expected.

However, running longer simulations with multiple seeds is absolutely easy with `prodsys`. We average our results at the end to calculate the WIP to expect by utilizing the post_processor of the runner, which stores all events of a simulation and has many useful methods for analyzing the simulation results:

```python
wip_values = []

for seed in range(5):
    production_system.run(2000, seed=seed)
    run_wip = production_system.post_processor.get_aggregated_wip_data()
    wip_values.append(run_wip)

print("WIP values for the simulation runs:", wip_values)
```

We can analyze these results easily with numpy seeing that the average WIP is 2.835, which is in between the two first runs, which gives us a more realistic expectation of the system's performance.

```python
import numpy as np
wip = np.array(wip_values).mean(axis=0)
print(wip)
```

These examples only cover the most basic functionalities of `prodsys`. For more elaborate guides that guide you through more of the package's features, please see the [tutorials](Tutorials/tutorial_0_overview.md). For a complete overview of the package's functionality, please see the [API reference](API_reference/API_reference_0_overview.md).

## Run prodsys as a webserver with REST API

prodsys cannot only be used as a python package, but can also be used as a webserver by interacting with its REST API. All features of prodsys are also available in the API and allow easy integration of prodsys in operative IT architectures. 

The API is based on the [FastAPI](https://fastapi.tiangolo.com/) framework and utilizes the models API of prodsys. To use prodsys as a webserver, you can use the official docker image which can be obtained from dockerhub:

```bash
docker pull sebbehrendt/prodsys
```

To start the API, run the following command:

```bash
docker run -p 8000:8000 sebbehrendt/prodsys
```

The API documentation is then available at `http://localhost:8000/docs`. 

## Contributing

`prodsys` is a new project and has therefore much room for improvement. Therefore, it would be a pleasure to get feedback or support! If you want to contribute to the package, either create issues on [prodsys' github page](https://github.com/sdm4fzi/prodsys) for discussing new features or contact me directly via [github](https://github.com/SebBehrendt) or [email](mailto:sebastian.behrendt@kit.edu).

### Development setup

For setting up a development environment, we recommend using `uv`. First, install `uv` using `pipx`:
```bash
pipx install uv
```

Then, create a virtual environment and install the project with its development dependencies:
```bash
uv venv
uv pip install -e ".[dev]"
```

To run the tests, use the following command:
```bash
uv run pytest
```

## License

The package is licensed under the [MIT license](LICENSE).

## Acknowledgements

We extend our sincere thanks to the German Federal Ministry for Economic Affairs and Climate Action
(BMWK) for supporting this research project 13IK001ZF “Software-Defined Manufacturing for the
automotive and supplying industry  [https://www.sdm4fzi.de/](https://www.sdm4fzi.de/)”.
