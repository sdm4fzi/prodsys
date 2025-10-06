from prodsys.simulation import request
from prodsys.models.dependency_data import DependencyType, LotDependencyData

class LotHandler:

    def _get_lot_dependency(self, process_request: request.Request) -> LotDependencyData:
        for dependency in process_request.required_dependencies:
            if dependency.data.dependency_type == DependencyType.LOT:
                return dependency.data
        return None

    def _request_matches(self, process_request: request.Request, potential_lot_request: request.Request) -> bool:
        if process_request.request_type == request.RequestType.PRODUCTION:
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
        lot_dependency = self._get_lot_dependency(process_request)
        if lot_dependency is None:
            return True
        if process_request.resource.data.capacity < lot_dependency.min_lot_size:
            raise ValueError(f"The capacity of the resource {process_request.resource.data.ID} is smaller than the min lot size {lot_dependency.min_lot_size}")
        if process_request.resource.get_free_capacity() < lot_dependency.min_lot_size:
            return False
        possible_requests_for_lot = self._get_possible_requests_for_lot(process_request)
        return len(possible_requests_for_lot) >= lot_dependency.min_lot_size - 1


    def _get_requests_to_fill_lot(self, process_request: request.Request, lot_dependency: LotDependencyData, possible_requests_for_lot: list[request.Request]) -> list[request.Request]:
        if process_request.resource.get_free_capacity() < lot_dependency.max_lot_size:
            max_requests_to_fill_lot = process_request.resource.get_free_capacity() - 1
        else:
            max_requests_to_fill_lot = lot_dependency.max_lot_size - 1
        num_requests_to_fill_lot = 0
        if len(possible_requests_for_lot) < max_requests_to_fill_lot:
            num_requests_to_fill_lot = len(possible_requests_for_lot)
        else:
            num_requests_to_fill_lot = max_requests_to_fill_lot
        return possible_requests_for_lot[:num_requests_to_fill_lot]

    def get_requests_of_lot(self, process_request: request.Request) -> list[request.Request]:
        lot_dependency = self._get_lot_dependency(process_request)
        if lot_dependency is None:
            return [process_request]
        possible_requests_for_lot = self._get_possible_requests_for_lot(process_request)
        # use control policy to sort the requests
        process_request.resource.controller.control_policy(possible_requests_for_lot)
        requests_to_fill_lot = self._get_requests_to_fill_lot(process_request, lot_dependency, possible_requests_for_lot)
        for lot_request in requests_to_fill_lot:
            process_request.resource.controller.requests.remove(lot_request)
        lot = [process_request] + requests_to_fill_lot
        return lot