import pytest
import random
import numpy as np
import prodsys
from prodsys.optimization.adapter_manipulation import reset_transformations


@pytest.fixture(autouse=True, scope="function")
def cleanup_test_state():
    """Fixture to clean up global test state before and after each test to avoid test pollution.
    
    This ensures that:
    - Transformation operations added during tests are cleaned up
    - Logging state is reset to default (WARNING)
    - Random state is reset to a known default (seed=0) to ensure deterministic behavior
    - Route caches are cleared to prevent cross-test route pollution
    """
    # Reset before test to ensure clean state
    reset_transformations()
    prodsys.set_logging("WARNING")  # Reset to default logging level
    # Set a default seed to ensure deterministic behavior
    # Individual tests can override this by setting their own seed
    np.random.seed(0)
    random.seed(0)
    
    # Clear route caches that persist across tests
    # These are class-level/module-level caches that can cause test pollution
    try:
        from prodsys.simulation.route_finder import RouteFinder
        RouteFinder.clear_cache()
    except ImportError:
        pass
    
    yield
    
    # Reset after test to clean up for next test
    reset_transformations()
    prodsys.set_logging("WARNING")  # Reset to default logging level
    # Reset random state to default for next test
    np.random.seed(0)
    random.seed(0)
    
    # Clear route caches again after test
    try:
        from prodsys.simulation.route_finder import RouteFinder
        RouteFinder.clear_cache()
    except ImportError:
        pass

