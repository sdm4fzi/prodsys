import os
from setuptools import setup, find_packages

# User-friendly description from README.md
current_directory = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(current_directory, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except Exception:
   long_description = ''

setup(
   name='prodsim',
   version='1.0.0',
   description='A useful module for production system simulation and optimization',
   license="MIT",
   long_description=long_description,
   author='Sebastian Behrendt',
   author_email='sebastian.behrendt@kit.edu',
   # url="http://www.foopackage.example/",
   packages=find_packages(),  #same as name
   install_requires=[
   'pydantic==1.10.2',
   'fastapi==0.88.0',
   'starlette==0.22.0',
   'uvicorn==0.20.0',
   'numpy==1.24.0',
   'pandas==1.5.2',
   'openpyxl==3.0.10',
   'plotly==5.11.0',
   'scipy==1.9.3',
   'simpy==4.0.1',
   'pm4py==2.3.3',
   'basyx-python-sdk==0.2.2',
   'strawberry-graphql==0.164.0',
   'simanneal==0.5.0',
   'deap==1.3.3',
   'gurobipy==10.0.1',
   'gymnasium==0.27.1',
   'hydra-core==1.3.2',
    ], #external packages as dependencies
   setup_requires=['pytest-runner'],
   tests_require=['pytest']
)