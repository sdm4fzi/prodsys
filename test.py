from functools import cached_property, cache
import pandas as pd

class Test:
    @cached_property
    # @property
    # @cache
    def test_func(self):
        df = pd.DataFrame(
            {"a": [1, 2, 3, 2, 5],
             "b": [1, 2, 3, 4, 5]}
        )
        time.sleep(0.1)
        return df


t = Test()
import time
start = time.perf_counter()

for _ in range(10):
    a = t.test_func
    print(id(a), a.shape)
    a = a.loc[a["a"] == 2]
    # a["new"] = a["b"]
    print(len(a))

print(time.perf_counter() - start)
