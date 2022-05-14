from uuid import uuid1, UUID
from time import perf_counter

sa = "7e41fa2e-d3c3-11ec-9d64-0242ac120002"
sb = "7e41fa2e-d3c3-11ec-9d64-0242ac120002"
a = UUID("7e41fa2e-d3c3-11ec-9d64-0242ac120002")
b = UUID("7e41fa2e-d3c3-11ec-9d64-0242ac120002")


t0 = perf_counter()
for _ in range(10000000):
    if sa == sb:
        pass

print(perf_counter() - t0)

t1 = perf_counter()

for _ in range(10000000):
    if a == b:
        pass
print(perf_counter() - t1)
