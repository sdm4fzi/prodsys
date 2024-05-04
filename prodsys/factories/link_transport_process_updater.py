from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel
from sympy import Union

from prodsys.factories import process_factory, source_factory, sink_factory, resource_factory, node_factory
from prodsys.simulation import process

if TYPE_CHECKING:
    from prodsys.simulation import resources, sink, source, node


class LinkTransportProcessUpdater(BaseModel):
    """
    Updater class that updates the links of `prodsys.simulation` LinkTransportProcess objects in the process factory based on the created node, resource, source and sink objects.

    Args:
        process_factory (process_factory.ProcessFactory): Factory that contains alll process objects.
        source_factory (source_factory.SourceFactory): Factory that contains all source objects.
        sink_factory (sink_factory.SinkFactory): Factory that contains all sink objects.
        resource_factory (resource_factory.ResourceFactory): Factory that contains all resource objects.
        node_factory (node_factory.NodeFactory): Factory that contains all node objects.
    """
    process_factory: process_factory.ProcessFactory
    source_factory: source_factory.SourceFactory
    sink_factory: sink_factory.SinkFactory
    resource_factory: resource_factory.ResourceFactory
    node_factory: node_factory.NodeFactory

    def update_links_with_objects(self):
        """
        The method updates the links of the LinkTransportProcess objects in the process factory with the created node, resource, source and sink objects from the respective factories.
        """
        for process_instance in self.process_factory.processes:
            if isinstance(process_instance, process.LinkTransportProcess):
                self.update_links(process_instance)

    def update_links(self, process_instance: process.LinkTransportProcess):
        link_id_list = process_instance.process_data.links
        links_list = []

        for link in link_id_list:
            start = link[0]
            end = link[1]

            start_obj = self.get_node_resource_source_sink(start)
            if not start_obj:
                raise ValueError(f"LinkTransportProcessUpdater: Could not find object with ID {start} for a link in Process {process_instance.process_data.ID}.")
            end_obj = self.get_node_resource_source_sink(end)
            if not end_obj:
                raise ValueError(f"LinkTransportProcessUpdater: Could not find object with ID {end} for a link in Process {process_instance.process_data.ID}.")

            links_list.append([start_obj, end_obj])

        process_instance.links = links_list

    def get_node_resource_source_sink(self, ID: str) -> Optional[Union[node.Node, resources.Resource, source.Source, sink.Sink]]:
        try:
            node = self.node_factory.get_node(ID)
            return node
        except IndexError:
            pass
        try:
            resource = self.resource_factory.get_resource(ID)
            return resource
        except IndexError:
            pass
        try:
            source = self.source_factory.get_source(ID)
            return source
        except IndexError:
            pass
        try:
            sink = self.sink_factory.get_sink(ID)
            return sink
        except IndexError:
            pass
