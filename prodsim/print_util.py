from __future__ import annotations

from . import sim


def print_simulation_info(env: sim.Environment, start_time: float, end_time: float):
    print("____________\n")

    print("simulated", env.now / 60 / 24, "days in", end_time - start_time, "seconds")
    print(f"generated material: {env.material_factory.material_counter} pieces - finished material: {sum([1 for material in env.material_factory.materials if material.finished])} pieces - throughput: {sum([1 for material in env.material_factory.materials if material.finished]) / env.now * 60 * 24} products / day")
    
    print("____________\n")

    for m in env.resource_factory.resources:
        print(m.ID, "ecetued: ", m.parts_made, "processes")

    print("____________\n")

    for q in env.queue_factory.queues:
        print(q.ID, "holds:", len(q.items), "pieces")