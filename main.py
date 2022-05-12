from process import ConcreteProcess
from time_model import FunctionTimeModel, TimeModel
from time_model import get_constant_list, get_normal_list, get_exponential_list
from dataclasses import dataclass, field
from typing import List

import json

FUNCTION_DICT: dict = {'normal': get_normal_list,
                       'constant': get_constant_list,
                       'exponential': get_exponential_list
                       }


@dataclass
class TimeModelFactory:
    data: dict
    time_models: List[TimeModel] = field(default_factory=lambda: [])

    def create_time_models(self):
        time_models = self.data['time_models']
        for _id, values in time_models.items():
            self.add_time_model(_id, values)

    def add_time_model(self, _id, values):
        self.time_models.append(FunctionTimeModel(parameters=values['parameters'],
                                                  batch_size=values['batch_size'],
                                                  distribution_function=FUNCTION_DICT[values['distribution_function']]
                                                  ))


if __name__ == '__main__':
    """    
    data = {
            'time_models': {
                'time_model1': {'parameters': (20, 5), 'batch_size': 100, 'distribution_function': 'normal'},
                'time_model2': {'parameters': (10, 5), 'batch_size': 100, 'distribution_function': 'constant'},
                'time_model3': {'parameters': (30, 5), 'batch_size': 100, 'distribution_function': 'exponential'},
            }
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)"""

    with open('data.json', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
    print(data)

    fac = TimeModelFactory(data)
    fac.create_time_models()


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






