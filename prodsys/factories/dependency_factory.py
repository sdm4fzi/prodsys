from prodsys.factories.primitive_factory import PrimitiveFactory
from prodsys.factories.process_factory import ProcessFactory
from prodsys.factories.product_factory import ProductFactory
from prodsys.factories.resource_factory import ResourceFactory
from prodsys.models.dependency_data import DEPENDENCY_TYPES, DependencyData, DependencyType
from prodsys.simulation.dependency import Dependency


class DependencyFactory:
    def __init__(self, process_factory: ProcessFactory, product_factory: ProductFactory, primitive_factory: PrimitiveFactory, resource_factory: ResourceFactory):
        """
        Initializes the DependencyFactory with the given factories.

        Args:
            process_factory (ProcessFactory): Factory that creates process objects.
            product_factory (ProductFactory): Factory that creates product objects.
            primitive_factory (PrimitiveFactory): Factory that creates primitive objects.
            resource_factory (ResourceFactory): Factory that creates resource objects.
        """
        self.process_factory = process_factory
        self.product_factory = product_factory
        self.primitive_factory = primitive_factory
        self.resource_factory = resource_factory
        self.dependencies = {}

    def create_dependencies(self, dependency_data_list: list[DEPENDENCY_TYPES]) -> list[Dependency]:
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
        return dependencies

    def create_dependency(self, dependency_data: DEPENDENCY_TYPES) -> Dependency:
        """
        Creates a dependency object based on the given dependency data.

        Args:
            dependency_data (DependencyData): Dependency data that is used to create the dependency object.

        Returns:
            Dependency: Created dependency object.
        """
        if dependency_data.dependency_type == DependencyType.PROCESS:
            process = self.process_factory.get_process(dependency_data.required_process)
            primitive = None
            resource = None
        elif dependency_data.dependency_type == DependencyType.RESOURCE:
            process = None
            primitive = None
            resource = self.resource_factory.get_resource(dependency_data.required_resource)
        elif dependency_data.dependency_type == DependencyType.PRIMITIVE:
            if dependency_data.required_primitive in self.product_factory.products:
                process = None
                primitive = self.product_factory.get_product(dependency_data.required_primitive)
                resource = None
            elif dependency_data.required_primitive in self.primitive_factory.primitives:
                process = None
                primitive = self.primitive_factory.get_primitive(dependency_data.required_primitive)
                resource = None 
            else:
                raise ValueError(f"Invalid primitive type for {dependency_data.required_primitive}")
        else:
            raise ValueError(f"Invalid dependency type for {dependency_data.dependency_type}")

        dependency = Dependency(
            env=self.resource_factory.env,
            data=dependency_data,
            required_process=process,
            required_primitive=primitive,
            required_resource=resource
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
        if not dependency_id in self.dependencies:
            raise ValueError(f"Dependency with ID {dependency_id} not found.")
        return self.dependencies[dependency_id]
    
    def inject_dependencies(self):
        """
        Injects dependencies into the product factory, process factory, and resource factory.
        """
        for resource in self.resource_factory.all_resources.values():
            dependencies = resource.data.dependency_ids
            dependencies= []
            for dependency_id in dependencies:
                dependency = self.get_dependency(dependency_id)
                resource.dependencies.append(dependency)

        for product in self.product_factory.products.values():
            dependencies = product.data.dependency_ids
            for dependency_id in dependencies:
                dependency = self.get_dependency(dependency_id)
                product.dependencies.append(dependency)

        for process in self.process_factory.processes.values():
            dependencies = process.data.dependency_ids
            for dependency_id in dependencies:
                dependency = self.get_dependency(dependency_id)
                process.dependencies.append(dependency)


    

    