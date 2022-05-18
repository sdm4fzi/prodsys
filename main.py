from time_model import TimeModelFactory
from state import StateFactory
from env import Environment
from process import ProcessFactory
from resource import ResourceFactory

import json

if __name__ == '__main__':

    env = Environment()

    with open('data.json', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
    print(data)

    tm_fac = TimeModelFactory(data)

    tm_fac.create_time_models()

    print(tm_fac.time_models)

    st_fac = StateFactory(data, env, tm_fac)
    st_fac.create_states()

    print(len(st_fac.states))

    pr_fac = ProcessFactory(data, tm_fac)
    pr_fac.create_processes()

    print(len(pr_fac.processes))

    # r = ConcreteResource(ID="99", description="Machine 1", env=env, processes=[pr_fac.processes[0], pr_fac.processes[1]])
    # st = st_fac.states[0]
    # print(st)
    # r.add_state(st)
    # print(r)
    #
    r_fac = ResourceFactory(data, env, pr_fac, st_fac)
    r_fac.create_resources()
    r_fac.start_resources()
    env.run(10000)
    for resource in r_fac.resources:
        print(resource.description, resource.parts_made)

    # TODO: check, why there are parts made, although no material is scheduled

    # TODO: add links of controller and resources in controller_registry

    # TODO: create material

    # TODO: add resources and material factories to environment

    # TODO: create graph with resources, process and material

    # TODO: create Router and Transformer class in environment


"""    screwing = ConcreteProcess(statistic=normal_list, description="This is a screwing process")
    gluing = ConcreteProcess(description="This is a gluing process", statistic=constant_list)
    welding = ConcreteProcess(description="This is a welding process", statistic=exp_list)

    wooden_plate = ConcreteMaterial(position = (1.0, 2.0), quality= 1.0, due_time = 60,
                                    description="This is a wooden plate")

    wooden_plate2 = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                     description="This is another old wooden plate")

    import math

    wood_screw = ConcreteMaterial(position = (30.0, 20.0), quality= 1.0, due_time = math.inf,
                                  description="This is a wood screw")

    combined_wood = ConcreteMaterial(position=(1.0, 2.5), quality=1.0, due_time=60,
                                     description="This is the combined wood")


    wooden_plate_with_screw = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                               description="This is the wood with screw")
                                               )
    finished_product = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                        description="This is the finished product")

    from igraph import Graph

    g = Graph()
    g.add_vertices(6)
    g.vs["Material"] = [wooden_plate, wooden_plate2, wood_screw, combined_wood, wooden_plate_with_screw, finished_product]
    g.add_edges([(0, 3), (1, 3), (0, 4), (2, 4), (3, 5), (4, 5)])
    g.es["Processes"] = [gluing, gluing, screwing, screwing, screwing, gluing]
    
    print(g.vs[0].attributes())
    a = g.vs.find(Material=wooden_plate)
    b = g.successors(a)
    print(a)
    print("123")
    print(g.vs[b[0]])
    print(g.vs[b[1]])"""






