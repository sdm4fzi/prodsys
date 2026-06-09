from __future__ import annotations

import re

from prodsys.simulation import request
from prodsys.models.dependency_data import (
    DependencyType,
    LinkLotDependencyData,
    LotDependencyData,
)
from prodsys.simulation.dependency import Dependency
from prodsys.models.resource_data import ResourceType
from prodsys.simulation.entities.lot import Lot

_WR_ORDER_RE = re.compile(r"_WR(\d{3})_")


def _work_request_order_id(entity) -> str | None:
    """Parse ``WR###`` from a product entity id (SICK naming)."""
    if entity is None:
        return None
    data = getattr(entity, "data", None)
    pid = getattr(data, "ID", None) if data is not None else None
    if not pid:
        return None
    match = _WR_ORDER_RE.search(str(pid))
    if not match:
        return None
    return f"WR{match.group(1)}"


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

    def _work_request_piece_count(self, process_request: request.Request) -> int | None:
        """How many products belong to this work request (SuTray size cap 34)."""
        wr_id = _work_request_order_id(process_request.requesting_item)
        if not wr_id:
            return None
        item = process_request.requesting_item
        router = getattr(item, "router", None)
        if router is None:
            return None
        ps = getattr(router, "production_system_data", None)
        if ps is not None and getattr(ps, "order_data", None):
            for order in ps.order_data:
                oid = str(getattr(order, "ID", ""))
                if oid in (wr_id, wr_id.removeprefix("WR")) or f"WR{oid}" == wr_id:
                    total = sum(
                        int(getattr(op, "quantity", 1) or 1)
                        for op in order.ordered_products
                    )
                    if total > 0:
                        return total
        product_factory = getattr(router, "product_factory", None)
        if product_factory is not None:
            count = sum(
                1
                for product in getattr(product_factory, "products", []) or []
                if _work_request_order_id(product) == wr_id
            )
            if count > 0:
                return count
        return None

    def _get_possible_requests_for_lot(self, process_request: request.Request) -> list[request.Request]:
        order_id = _work_request_order_id(process_request.requesting_item)
        possible_requests_for_lot = []
        for open_request in process_request.resource.controller.requests:
            if open_request is process_request:
                continue
            if not self._request_matches(process_request, open_request):
                continue
            if order_id is not None:
                other_order = _work_request_order_id(open_request.requesting_item)
                if other_order != order_id:
                    continue
            possible_requests_for_lot.append(open_request)
        return possible_requests_for_lot

    def _effective_min_lot_size(
        self,
        lot_dependency: LotDependencyData,
        process_request: request.Request,
    ) -> int:
        """Target batch size for a SuTray move (full WR, capped by link min)."""
        configured = int(lot_dependency.min_lot_size)
        if configured <= 1:
            return 1
        wr_pieces = self._work_request_piece_count(process_request)
        if wr_pieces is not None and wr_pieces > 0:
            return min(configured, wr_pieces)
        return configured

    def is_lot_feasible(self, process_request: request.Request) -> bool:
        lot_dependency = self._get_lot_dependency_data(process_request)
        if lot_dependency is None:
            return True
        possible_requests_for_lot = self._get_possible_requests_for_lot(process_request)
        effective_min = self._effective_min_lot_size(lot_dependency, process_request)
        if process_request.resource.data.capacity < effective_min:
            raise ValueError(
                f"The capacity of the resource {process_request.resource.data.ID} "
                f"is smaller than the effective min lot size {effective_min}"
            )
        if process_request.resource.get_free_capacity() < effective_min:
            return False
        if process_request.request_type == request.RequestType.TRANSPORT:
            if (
                process_request.target_queue.is_full
                or process_request.target_queue.free_space() < effective_min
            ):
                return False
        return len(possible_requests_for_lot) >= effective_min - 1


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