from process import ConcreteProcess
from time_model import FunctionTimeModel
from time_model import get_constant_list, get_normal_list, get_exponential_list

from material import ConcreteMaterial
from uuid import uuid1

if __name__ == '__main__':
    normal_list = FunctionTimeModel(parameters=(20, 5,), batch_size=100, distribution_function=get_normal_list)
    constant_list = FunctionTimeModel(parameters=(20, 5,), batch_size=100, distribution_function=get_constant_list)
    exp_list = FunctionTimeModel(parameters=(20, 5,), batch_size=100, distribution_function=get_exponential_list)
    screwing = ConcreteProcess(statistic=normal_list, description="This is a screwing process", _id=uuid1())
    gluing = ConcreteProcess(description="This is a gluing process", statistic=constant_list, _id=uuid1())
    welding = ConcreteProcess(description="This is a welding process", statistic=exp_list, _id=uuid1())

    wooden_plate = ConcreteMaterial(position = (1.0, 2.0), quality= 1.0, due_time = 60,
                                    description="This is a wooden plate", _id=uuid1())

    wooden_plate2 = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                     description="This is another old wooden plate", _id=uuid1())

    import math

    wood_screw = ConcreteMaterial(position = (30.0, 20.0), quality= 1.0, due_time = math.inf,
                                  description="This is a wood screw", _id=uuid1())

    combined_wood = ConcreteMaterial(position=(1.0, 2.5), quality=1.0, due_time=60,
                                     description="This is the combined wood", _id=uuid1())


    wooden_plate_with_screw = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                               description="This is the wood with screw", _id=uuid1()
                                               )
    finished_product = ConcreteMaterial(position=(1.0, 2.5), quality=0.75, due_time=60,
                                        description="This is the finished product", _id=uuid1())

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
    print(g.vs[b[1]])






