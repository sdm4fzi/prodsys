from env import Environment
from material import MaterialFactory
from store import QueueFactory
from resources import ResourceFactory

def print_simulation_info(_env: Environment, m_fac: MaterialFactory, r_fac: ResourceFactory, q_fac: QueueFactory, start_time: float, end_time: float):
    print("____________\n")

    print("simulated", _env.now / 60 / 24, "days in", end_time - start_time, "seconds")
    print(f"generated material: {m_fac.material_counter} pieces - finished material: {sum([1 for material in m_fac.materials if material.finished])} pieces - throughput: {sum([1 for material in m_fac.materials if material.finished]) / _env.now * 60 * 24} products / day")
    
    print("____________\n")

    for m in r_fac.resources:
        print(m.ID, "ecetued: ", m.parts_made, "processes")

    print("____________\n")

    for q in q_fac.queues:
        print(q.ID, "holds:", len(q.items), "pieces")