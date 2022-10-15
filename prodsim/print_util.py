from __future__ import annotations

from . import env


def print_simulation_info(_env: env.Environment, start_time: float, end_time: float):
    print("____________\n")

    print("simulated", _env.now / 60 / 24, "days in", end_time - start_time, "seconds")
    print(f"generated material: {_env.material_factory.material_counter} pieces - finished material: {sum([1 for material in _env.material_factory.materials if material.finished])} pieces - throughput: {sum([1 for material in _env.material_factory.materials if material.finished]) / _env.now * 60 * 24} products / day")
    
    print("____________\n")

    for m in _env.resource_factory.resources:
        print(m.ID, "ecetued: ", m.parts_made, "processes")

    print("____________\n")

    for q in _env.queue_factory.queues:
        print(q.ID, "holds:", len(q.items), "pieces")