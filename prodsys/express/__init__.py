"""
This module contains the `prodsys.express` API with classes and functions to easily specify all parameters of a production system. This API is completely compatible with `prodsys.models` and every object can be converted to a data object from `prodsys.models` using the `to_model` method.

The express API is more convenient to use than the `prodsys.models` API because the express API nests the objects in a tree structure, which makes it easier to work with when instantiating production system programatically. 

However, the express API does not support all features of the `prodsys.models` API and saved data is more complicated to review because of the nesting.

Recommended is to use the API for programmatically specifying a production system but saving the data in the `prodsys.models` format with the `ProductionSystemAdapter`.

The following modules are available:

- `prodsys.express.core`: Contains the abstract base class for express objects.	
- `prodsys.express.product`: Contains classes to specify products.
- `prodsys.express.process`: Contains classes to specify processes.
- `prodsys.express.production_system`: Contains classes to specify a production system.
- `prodsys.express.resources`: Contains classes to specify resources.
- `prodsys.express.sink`: Contains classes to specify sinks.
- `prodsys.express.source`: Contains classes to specify sources.
- `prodsys.express.state`: Contains classes to specify states.
- `prodsys.express.time_model`: Contains classes to specify time models.

"""
from prodsys.express.core import ExpressObject
from prodsys.express.time_model import (
    SampleTimeModel,
    ScheduledTimeModel,
    FunctionTimeModel,
    DistanceTimeModel,
    SequentialTimeModel,
    ManhattanDistanceTimeModel,
)
from prodsys.express.state import SetupState, BreakDownState, ProcessBreakdownState
from prodsys.express.node import Node
from prodsys.express.process import (
    ProductionProcess,
    CapabilityProcess,
    RequiredCapabilityProcess,
    TransportProcess,
    LinkTransportProcess,
)
from prodsys.express.resources import ProductionResource, TransportResource
from prodsys.express.product import Product
from prodsys.express.source import Source
from prodsys.express.sink import Sink
from prodsys.express.production_system import ProductionSystem
