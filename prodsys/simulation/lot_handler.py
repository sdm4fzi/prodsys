from prodsys.simulation import request
from prodsys.models.dependency_data import (
    DependencyType,
    LinkLotDependencyData,
    LotDependencyData,
)
from prodsys.simulation.dependency import Dependency
from prodsys.models.resource_data import ResourceType
from prodsys.simulation.entities.lot import Lot

class LotHandler:

    def _get_lot_dependency(self, process_request: request.Request) -> Dependency:
        for dependency in process_request.required_dependencies:
            if dependency.data.dependency_type == DependencyType.LOT:
                return dependency
        return None

    @staticmethod
    def _resolve_link_lot_dependency(
        dep_data: LotDependencyData,
        process_request: request.Request,
    ) -> LotDependencyData:
        """Specialise a :class:`LinkLotDependencyData` to the request's link.

        For a transport request, look up the (origin, target) node IDs and
        return a plain :class:`LotDependencyData` carrying the link-specific
        ``(min_lot_size, max_lot_size)``.  For non-transport requests (or
        when the request has no resolvable origin/target), fall back to the
        inherited base values so the behaviour collapses to the original
        per-process lot size.
        """
        if not isinstance(dep_data, LinkLotDependencyData):
            return dep_data

        origin_id = None
        target_id = None
        if process_request.request_type == request.RequestType.TRANSPORT:
            origin = getattr(process_request, "origin", None)
            target = getattr(process_request, "target", None)
            origin_id = getattr(getattr(origin, "data", None), "ID", None)
            target_id = getattr(getattr(target, "data", None), "ID", None)
        if origin_id is None or target_id is None:
            min_size, max_size = dep_data.min_lot_size, dep_data.max_lot_size
        else:
            min_size, max_size = dep_data.get_link_lot_sizes(origin_id, target_id)

        return LotDependencyData(
            ID=f"{dep_data.ID}__{origin_id}->{target_id}",
            description=(
                f"Link-resolved lot dependency for {origin_id}->{target_id}"
                if origin_id and target_id
                else f"Link-resolved lot dependency (fallback) for {dep_data.ID}"
            ),
            dependency_type=DependencyType.LOT,
            min_lot_size=min_size,
            max_lot_size=max_size,
            input_output=dep_data.input_output,
        )

    def _get_lot_dependency_data(self, process_request: request.Request) -> LotDependencyData:
        lot_dependencies = []
        for dependency in process_request.required_dependencies:
            if dependency.data.dependency_type == DependencyType.LOT:
                # ``LinkLotDependencyData`` declares a different lot size per
                # link; resolve to that link's (min, max) before any feasibility
                # / bundling logic runs.
                lot_dependencies.append(
                    self._resolve_link_lot_dependency(dependency.data, process_request)
                )
        if len(lot_dependencies) == 0:
            return None
        if len(lot_dependencies) == 1:
            return lot_dependencies[0]
        # if there are multiple lot dependencies, we need to combine them into one lot dependency
        combined_lot_dependency = LotDependencyData(
            ID="combined_lot_dependency",
            description="Combined lot dependency",
            dependency_type=DependencyType.LOT,
            min_lot_size=min(lot_dependency.min_lot_size for lot_dependency in lot_dependencies),
            max_lot_size=max(lot_dependency.max_lot_size for lot_dependency in lot_dependencies),
        )
        return combined_lot_dependency

    def lot_required(self, process_request: request.Request) -> bool:
        if process_request.request_type not in [request.RequestType.PRODUCTION, request.RequestType.TRANSPORT, request.RequestType.PROCESS_MODEL]:
            return False

        if process_request.request_type == request.RequestType.PROCESS_MODEL and process_request.resource.data.resource_type == ResourceType.SYSTEM:
            return False
        
        if not self._get_lot_dependency_data(process_request):
            return False
        return True

    def _request_matches(self, process_request: request.Request, potential_lot_request: request.Request) -> bool:
        if process_request.request_type == request.RequestType.PRODUCTION or process_request.request_type == request.RequestType.PROCESS_MODEL:
            return process_request.process == potential_lot_request.process
        elif process_request.request_type == request.RequestType.TRANSPORT:
            return process_request.process == potential_lot_request.process and process_request.origin_queue == potential_lot_request.origin_queue and process_request.target_queue == potential_lot_request.target_queue
        else:
            return False

    def _get_possible_requests_for_lot(self, process_request: request.Request) -> list[request.Request]:
        possible_requests_for_lot = []
        for open_request in process_request.resource.controller.requests:
            if open_request is process_request:
                continue
            if self._request_matches(process_request, open_request):
                possible_requests_for_lot.append(open_request)
        return possible_requests_for_lot
    
    def is_lot_feasible(self, process_request: request.Request) -> bool:
        lot_dependency = self._get_lot_dependency_data(process_request)
        if lot_dependency is None:
            return True
        if process_request.resource.data.capacity < lot_dependency.min_lot_size:
            raise ValueError(f"The capacity of the resource {process_request.resource.data.ID} is smaller than the min lot size {lot_dependency.min_lot_size}")
        if process_request.resource.get_free_capacity() < lot_dependency.min_lot_size:
            return False
        # if process_request.target_queue.is_full or process_request.target_queue.free_space() < lot_dependency.min_lot_size: # avoids that reservations don't go through
        #     return False
        if process_request.request_type == request.RequestType.TRANSPORT:
            if process_request.target_queue.is_full or process_request.target_queue.free_space() < lot_dependency.min_lot_size:
                return False
        possible_requests_for_lot = self._get_possible_requests_for_lot(process_request)
        num_possible = len(possible_requests_for_lot)
        return num_possible >= lot_dependency.min_lot_size - 1


    def _get_requests_to_fill_lot(self, process_request: request.Request, lot_dependency: LotDependencyData, possible_requests_for_lot: list[request.Request]) -> list[request.Request]:
        if process_request.resource.get_free_capacity() < lot_dependency.max_lot_size:
            max_requests_to_fill_lot = process_request.resource.get_free_capacity() - 1
        elif process_request.request_type == request.RequestType.TRANSPORT and process_request.target_queue.free_space() < lot_dependency.max_lot_size:
            max_requests_to_fill_lot = process_request.target_queue.free_space() - 1
        else:
            max_requests_to_fill_lot = lot_dependency.max_lot_size - 1
        num_requests_to_fill_lot = 0
        if len(possible_requests_for_lot) < max_requests_to_fill_lot:
            num_requests_to_fill_lot = len(possible_requests_for_lot)
        else:
            num_requests_to_fill_lot = max_requests_to_fill_lot
        if num_requests_to_fill_lot < 0:
            raise ValueError(f"The number of requests to fill the lot is negative: {num_requests_to_fill_lot}")
        return possible_requests_for_lot[:num_requests_to_fill_lot]

    def get_lot_request(self, process_request: request.Request) -> request.Request:
        lot_dependency = self._get_lot_dependency_data(process_request)
        if lot_dependency is None:
            return [process_request]
        possible_requests_for_lot = self._get_possible_requests_for_lot(process_request)
        # use control policy to sort the requests
        process_request.resource.controller.control_policy(possible_requests_for_lot)
        requests_to_fill_lot = self._get_requests_to_fill_lot(process_request, lot_dependency, possible_requests_for_lot)
        for lot_request in requests_to_fill_lot:
            process_request.resource.controller.requests.remove(lot_request)
        lot_requests = [process_request] + requests_to_fill_lot
        lot_entities = [request.entity for request in lot_requests]
        all_completed_events = [request.completed for request in lot_requests]

        lot = Lot(
            all_completed_events=all_completed_events,
            entities=lot_entities,
            resolved_dependency=self._get_lot_dependency(process_request),
            required_dependencies=process_request.required_dependencies,
        )
        process_request.entity = lot
        process_request.required_dependencies = lot.dependencies
        return process_request