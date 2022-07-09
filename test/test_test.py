from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class TimeModel:
    process_time: int


@dataclass
class Process:
    name: str
    time_model: TimeModel

    def get_time_model(self) -> TimeModel:
        return self.time_model

@dataclass
class Request:
    _process: Process
    _material: str
    _resource: str
    _started_waiting: int
    _resource_pos: Tuple[float]
    _target_pos: Tuple[float]



def SPT_control_policy(current: List[Request]) -> None:
    current.sort(key=lambda x: x._process.get_time_model().process_time)

def sort_LIFO(current: List[Request]) -> List[Request]:
    current.reverse()
    # current = list(reversed(current))


R1 = Request(Process("P1", TimeModel(10)), "M1", "R", 5, (0,0), (10, 5))
R2 = Request(Process("P2", TimeModel(30)), "M1", "R", 15, (10, 5), (10, 10))
R3 = Request(Process("P1", TimeModel(10)), "M1", "R", 10, (0, 0), (0, 0))
R4 = Request(Process("P3", TimeModel(20)), "M1", "R", 20)
R5 = Request(Process("P2", TimeModel(30)), "M1", "R", 25)

requests = [R1, R2, R3, R4, R5]

for r in requests:
    print(r)

# sort_LIFO(requests)
SPT_control_policy(requests)

print("__________")

for r in requests:
    print(r)

requests.pop(0)


print("__________")


for r in requests:
    print(r)