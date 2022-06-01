import simpy
from dataclasses import dataclass


@dataclass
class A:
    i: int

a1 = A(2)
a2 = A(3)


env = simpy.Environment()
s = simpy.FilterStore(env, capacity=2)

s.put(a1)
s.put(a2)

a = s.get(filter=lambda s: s is a2)

print(a.value)