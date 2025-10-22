from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Union


from prodsys.factories import (
    process_factory,
    source_factory,
    sink_factory,
    resource_factory,
    node_factory,
    port_factory,
)
from prodsys.simulation import process

if TYPE_CHECKING:
    from prodsys.simulation import resources, sink, source, node, port


class LinkTransportProcessUpdater:
    """
    Updater class that updates the links of `prodsys.simulation` LinkTransportProcess objects in the process factory based on the created node, resource, source and sink objects.

    Args:
        process_factory (process_factory.ProcessFactory): Factory that contains alll process objects.
        source_factory (source_factory.SourceFactory): Factory that contains all source objects.
        sink_factory (sink_factory.SinkFactory): Factory that contains all sink objects.
        resource_factory (resource_factory.ResourceFactory): Factory that contains all resource objects.
        node_factory (node_factory.NodeFactory): Factory that contains all node objects.
    """

    def __init__(
        self,
        process_factory: process_factory.ProcessFactory,
        source_factory: source_factory.SourceFactory,
        sink_factory: sink_factory.SinkFactory,
        resource_factory: resource_factory.ResourceFactory,
        node_factory: node_factory.NodeFactory,
        queue_factory: port_factory.QueueFactory,
    ):
        self.process_factory = process_factory
        self.source_factory = source_factory
        self.sink_factory = sink_factory
        self.resource_factory = resource_factory
        self.node_factory = node_factory
        self.queue_factory = queue_factory

    def update_links_with_objects(self):
        """
        The method updates the links of the LinkTransportProcess objects in the process factory with the created node, resource, source and sink objects from the respective factories.
        """
        for process_instance in self.process_factory.processes.values():
            if isinstance(process_instance, process.LinkTransportProcess):
                self.update_links(process_instance)

    def update_links(self, process_instance: process.LinkTransportProcess):
        link_id_list = process_instance.data.links
        links_list = []

        for link in link_id_list:
            start = link[0]
            end = link[1]

            start_obj = self.get_node_resource_source_sink(start)
            if not start_obj:
                raise ValueError(
                    f"LinkTransportProcessUpdater: Could not find object with ID {start} for a link in Process {process_instance.data.ID}."
                )
            if hasattr(start_obj, "ports"):
                # create links from possible starts
                possible_starts = self.get_possible_ports(start_obj)
            else:
                possible_starts = [start_obj]
            end_obj = self.get_node_resource_source_sink(end)
            if not end_obj:
                raise ValueError(
                    f"LinkTransportProcessUpdater: Could not find object with ID {end} for a link in Process {process_instance.data.ID}."
                )

            if hasattr(end_obj, "ports"):
                # create links from possible ends
                possible_ends = self.get_possible_ports(end_obj)
            else:
                possible_ends = [end_obj]

            for start in possible_starts:
                for end in possible_ends:
                    links_list.append([start, end])

        process_instance.links = links_list

    def get_possible_ports(self, obj: Union[resources.Resource, source.Source, sink.Sink]) -> list[port.Queue]:
        ports = []
        for port in obj.ports:
            ports.append(port)
        return ports

    def get_node_resource_source_sink(
        self, ID: str
    ) -> Optional[Union[node.Node, resources.Resource, source.Source, sink.Sink]]:
        try:
            node = self.node_factory.get_node(ID)
            return node
        except IndexError:
            pass
        try:
            resource = self.resource_factory.get_resource(ID)
            return resource
        except KeyError:
            pass
        try:
            source = self.source_factory.get_source(ID)
            return source
        except ValueError:
            pass
        try:
            sink = self.sink_factory.get_sink(ID)
            return sink
        except KeyError:
            pass
        try:
            port = self.queue_factory.get_queue(ID)
            return port
        except KeyError:
            pass
