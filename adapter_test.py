from __future__ import annotations

import prodsim

if __name__ == '__main__':

    adapter_object = prodsim.adapter.JsonAdapter()

    adapter_object.read_data('data/simple_example.json')

    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(30000)