
- Prodsys ProductionSystem is called ProdsysModel
- Sequential Processes which are containers for a sequence of processes a resource performs
- Create ProducitonSystem, which is a resource with subresources, but can be used interchangeably
- There Exists a ProcessModel (inherits from Process), which can model sequences of processes as a directed acyclic graph (DAG), e.g. Process 1 -> Process 2 -> Process 3 or more complex structures
    - ProcessModel can contain other ProcessModels
    - An ProcessModelHandler exists in the Controller, similar to production / transport process handlers
    - Product should use such a ProcessModel as a process, which can be easily instantiated with a list of ids or ProcessModel process
- Loading Processes, which can be chained in sequential processes or mandatory dependencies of some processes
- (Dependencies can have attribtues like before, after, parallel)
- Products can request processes of resources and systems. 
- If a resource process is requested but it is in a system, the process interaction is with the system (allows to model robot cells with handlings or complex machines with loading processes)
- Resource Routing must consider this with ports of systems and routing inside systems, which resources can be used and how to reach it (potential system boundaries must be crossed: origin -> transport -> system port -> transport -> target) (from subsystem to other subsysstem even more complex -> find a way to cross multiple system boundaries and find these logical paths easily)

- ProcessModel Class should implement the behavior 

Data Models New:
- ProcessModel (inherits from Process)
- SequentialProcess (inherits from ProcessModel)
- ProductionSystem (inherits from Resource)

Data Models to Update:
- Product (use ProcessModel as process)
- ProductionSystem is renamed to Model (inherits from Resource)