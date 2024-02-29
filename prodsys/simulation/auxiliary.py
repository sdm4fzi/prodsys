from __future__ import annotations

from abc import ABC
from enum import Enum
from collections.abc import Iterable
from typing import List, Union, Optional, TYPE_CHECKING, Generator

from pydantic import BaseModel, Field, Extra

import logging
logger = logging.getLogger(__name__)

from simpy import events

from pydantic import BaseModel

from prodsys.simulation import (
    process,
    request,
    router,
    sim,
    product
)



from prodsys.models import auxiliary_data, product_data


class Auxiliary(BaseModel):
    """
    Class that represents a product in the discrete event simulation. For easier instantion of the class, use the ProductFactory at prodsys.factories.product_factory.

    Args:
        env (sim.Environment): prodsys simulation environment.
        auxilary_data (auxilary.Auxilary): Auxilary data of the product.
    """

    env: sim.Environment
    auxiliary_data: auxiliary_data.Auxiliary
    auxiliary_router: router.Router
    transport_process: process.Process
    current_location: product.Location = Field(default=None, init=False)
    current_product: product.Product = Field(default=None, init=False)
    requested: events.Event = Field(default=events.Event(env), init=False)
    ready_to_use: events.Event = Field(default=events.Event(env), init=False)

    class Config:
        arbitrary_types_allowed = True

    def request(self, process_request: request.TransportResquest) -> None:
        """
        Request the auxiliary component to be transported to a Location of a product.

        Args:
            process_request (request.Request): The request to be processed.
        """
        self.current_product = process_request.product
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": process_request.resource.data.ID, "event": f"Got requested by {process_request.product.product_data.ID}"})
        if not self.requested.triggered:
            logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": process_request.resource.data.ID, "event": "Triggered requested event"})
            self.requested.succeed()

    def update_location(self, location: product.Location):
        """
        Updates the location of the product object.

        Args:
            resource (Location): Location of the product object.
        """
        self.current_location = location
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "resource": self.current_location.data.ID, "event": f"Updated location to {self.current_location.data.ID}"})

    def process_product(self):
        self.finished_process = events.Event(self.env)
        logger.debug({"ID": self.auxiliary_data.ID, "sim_time": self.env.now, "event": f"Start processing of auxiliary component"})
        while True:
            # 1. wait until requested by a process (use logic from controller loops here)
            yield self.requested
            self.requested = events.Event(self.env)
            # 3. transport to product based on request to route transport process to transport auxiliary to product 
            # (based on current location axuiliary and product location)
            # 4. yield until transport process is finished
            # 5. update location of auxiliary to product location, trigger ready_to_use event to conitnue processing of the product
            self.ready_to_use.succeed()
            # 6. yield until product is finished processing (maybe use also a release event....) -> remove auxiliary from product
            # 7. update the location of the auxiliary
            # 8. request transport to storage location
        # important to check:
        # - if transported, auxiliaries should'nt be placed in queues, like with products -> change logic in controllers to make case distinction.
        # - transport of auxiliaries (when not attached to products) should be logged similarly as products -> check if this is the case
