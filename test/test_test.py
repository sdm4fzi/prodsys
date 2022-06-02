# import simpy
# from dataclasses import dataclass
#
#
# @dataclass
# class A:
#     i: int
#
# a1 = A(2)
# a2 = A(3)
#
#
# env = simpy.Environment()
# s = simpy.FilterStore(env, capacity=2)
#
# s.put(a1)
# s.put(a2)
#
# a = s.get(filter=lambda s: s is a2)
#
# print(a.value)

from collections.abc import Iterable

def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x

list2d = [[1,2,3], [4,[1, 2], 5,6], [7], [8,9]]
merged = flatten(list2d)
print(list2d)
print(merged)
for d in merged:
    print(d)
print(list(merged))