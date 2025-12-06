from prodsys.factories.primitive_factory import PrimitiveFactory
from prodsys.factories.process_factory import ProcessFactory
from prodsys.factories.product_factory import ProductFactory
from prodsys.factories.resource_factory import ResourceFactory
from prodsys.factories.node_factory import NodeFactory
from prodsys.models.dependency_data import DEPENDENCY_TYPES, DependencyType
from prodsys.simulation.dependency import Dependency
from prodsys.models.product_data import ProductData
from prodsys.models import product_data

class DependencyFactory:
    def __init__(self, process_factory: ProcessFactory, product_factory: ProductFactory, primitive_factory: PrimitiveFactory, resource_factory: ResourceFactory, node_factory: NodeFactory):
        """
        Initializes the DependencyFactory with the given factories.

        Args:
            process_factory (ProcessFactory): Factory that creates process objects.
            product_factory (ProductFactory): Factory that creates product objects.
            primitive_factory (PrimitiveFactory): Factory that creates primitive objects.
            resource_factory (ResourceFactory): Factory that creates resource objects.
            node_factory (NodeFactory): Factory that creates node objects.
        """
        self.process_factory = process_factory
        self.product_factory = product_factory
        self.primitive_factory = primitive_factory
        self.resource_factory = resource_factory
        self.node_factory = node_factory
        self.dependencies: dict[str, Dependency] = {}
        
    def check_product_dependencies(self,dependency_data: DEPENDENCY_TYPES, product_data: list[ProductData]):
        if not dependency_data.dependency_type == DependencyType.ASSEMBLY:
            return
        for product_d in product_data:
            if(product_d.ID == dependency_data.required_entity): 
                product_d.becomes_consumable = True
                
    def create_dependencies(self, dependency_data_list: list[DEPENDENCY_TYPES], product_data: ProductData) -> list[Dependency]:
        """
        Creates a list of dependency objects based on the given dependency data.

        Args:
            dependency_data_list (list[DependencyData]): List of dependency data that is used to create the dependency objects.

        Returns:
            list[Dependency]: List of created dependency objects.
        """
        dependencies = []
        for dependency_data in dependency_data_list:
            dependencies.append(self.create_dependency(dependency_data))
            self.check_product_dependencies(dependency_data, product_data)
        return dependencies

    def create_dependency(self, dependency_data: DEPENDENCY_TYPES) -> Dependency:
        """
        Creates a dependency object based on the given dependency data.

        Args:
            dependency_data (DependencyData): Dependency data that is used to create the dependency object.

        Returns:
            Dependency: Created dependency object.
        """
        process, primitive, resource, node = None, None, None, None
        if dependency_data.dependency_type == DependencyType.PROCESS:
            process = self.process_factory.get_process(dependency_data.required_process)
            node = self.node_factory.get_node(dependency_data.interaction_node)
        elif dependency_data.dependency_type == DependencyType.RESOURCE:
            resource = self.resource_factory.get_resource(dependency_data.required_resource)
            if dependency_data.interaction_node is not None:
                node = self.node_factory.get_node(dependency_data.interaction_node)
            else:
                node = None
        elif dependency_data.dependency_type == DependencyType.ASSEMBLY or dependency_data.dependency_type == DependencyType.DISASSEMBLY:
            try:
                primitive = self.product_factory.get_product_init(dependency_data.required_entity)
            except Exception as e:
                pass
            if(primitive == None):
                try:
                    primitive = self.primitive_factory.get_primitive_with_type(dependency_data.required_entity)
                except Exception as e:
                    raise ValueError(f"Primitive with ID {dependency_data.required_entity} not found.") from e  
        elif dependency_data.dependency_type == DependencyType.TOOL:
            try:
                primitive = self.primitive_factory.get_primitive_with_type(dependency_data.required_entity)
            except Exception as e:
                raise ValueError(f"Primitive with ID {dependency_data.required_entity} not found.") from e  
        elif dependency_data.dependency_type == DependencyType.LOT:
            pass
        else:
            raise ValueError(f"Invalid dependency type for {dependency_data.dependency_type}: {dependency_data.dependency_type}")

        dependency = Dependency(
            env=self.resource_factory.env,
            data=dependency_data,
            required_process=process,
            required_primitive=primitive,
            required_resource=resource,
            interaction_node=node,
        )
        self.dependencies[dependency_data.ID] = dependency
        return dependency

    def get_dependency(self, dependency_id: str) -> Dependency:
        """
        Returns the dependency object with the given ID.

        Args:
            dependency_id (str): ID of the dependency object to be returned.

        Returns:
            Dependency: Dependency object with the given ID.
        """
        if dependency_id not in self.dependencies:
            raise ValueError(f"Dependency with ID {dependency_id} not found.")
        return self.dependencies[dependency_id]

    def inject_dependencies(self):
        """
        Injects dependencies into the product factory, process factory, and resource factory.
        """
        for resource in self.resource_factory.all_resources.values():
            dependencies = resource.data.dependency_ids
            for dependency_id in dependencies:
                dependency = self.get_dependency(dependency_id)
                resource.dependencies.append(dependency)

        self.product_factory.dependency_factory = self

        for process in self.process_factory.processes.values():
            if not hasattr(process.data, "dependency_ids"):
                process.dependencies = []
                continue
            dependencies = process.data.dependency_ids
            for dependency_id in dependencies:
                dependency = self.get_dependency(dependency_id)
                process.dependencies.append(dependency)
