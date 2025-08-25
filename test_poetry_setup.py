#!/usr/bin/env python3

# Test script that only imports basic components to test if Poetry setup works

try:
    print("Testing basic imports...")
    
    # Test core imports
    import simpy
    print("✓ simpy imported successfully")
    
    import pandas as pd
    print("✓ pandas imported successfully")
    
    import numpy as np
    print("✓ numpy imported successfully")
    
    from pydantic import BaseModel
    print("✓ pydantic imported successfully")
    
    print("\n✅ All basic dependencies are working!")
    print("Poetry setup is successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
