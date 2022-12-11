from fastapi import FastAPI
from prodsim.data_structures import time_model_data

app = FastAPI()

data_base = [
    time_model_data.HistoryTimeModelData(
        ID="test time_model",
        description="test time_model",
        type=time_model_data.TimeModelEnum.HistoryTimeModel,
        history=[1, 2, 3, 4, 5],
    ),
    time_model_data.FunctionTimeModelData(
        ID="test time_model",
        description="test time_model",
        type=time_model_data.TimeModelEnum.FunctionTimeModel,
        distribution_function=time_model_data.FunctionTimeModelEnum.Constant,
        parameters=[1, 2],
    ),
]


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/history_time_model", response_model=time_model_data.HistoryTimeModelData)
async def get_time_model_history() -> time_model_data.HistoryTimeModelData:

    return data_base[0]

@app.get("/function_time_model", response_model=time_model_data.FunctionTimeModelData)
async def get_time_model_function() -> time_model_data.FunctionTimeModelData:
    return data_base[1]
