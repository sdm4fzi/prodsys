from typing import Dict, Union
from pydantic import BaseModel, validator
import datetime

from prodsim import adapters

import pandas as pd


class ProcessTime(BaseModel):
    machineDurationGroup: str
    taskDurationGroup: str
    duration: datetime.datetime

    @validator("duration", pre=True)
    def duration_to_timedelta(cls, v):
        # return datetime.datetime.strptime(v, "%HH:%MM:%SS")
        return datetime.datetime.strptime(v[3:], "%H:%M:%S.%f")


class FlexisDataFrames(BaseModel):
    ApplicationName: pd.DataFrame
    Capability: pd.DataFrame
    Customer: pd.DataFrame
    Product: pd.DataFrame
    OrderType: pd.DataFrame
    JobType: pd.DataFrame
    Order: pd.DataFrame
    Location: pd.DataFrame
    Machine: pd.DataFrame
    TaskType: pd.DataFrame
    WorkPlan: pd.DataFrame
    SetupTime: pd.DataFrame
    ProcessTime: pd.DataFrame
    TransitionTime: pd.DataFrame
    CalendarParameter: pd.DataFrame
    DayPattern: pd.DataFrame
    Shift: pd.DataFrame
    NonworkingDay: pd.DataFrame
    Constraint: pd.DataFrame
    LinkType: pd.DataFrame
    Link: pd.DataFrame

    class Config:
        arbitrary_types_allowed = True


class FlexisAdapter(adapters.Adapter):
    def read_data(self, file_path: str):
        # read excel file
        xls = pd.ExcelFile(file_path)
        df_machine = pd.read_excel(xls, "Machine")  # type: ignore False
        input_data = {}
        for sheet_name in xls.sheet_names:
            input_data[sheet_name] = pd.read_excel(xls, sheet_name)  # type: ignore False

        flexis_data_frames = FlexisDataFrames(**input_data)
        self.initialize_time_models(flexis_data_frames)

    def initialize_time_models(self, flexis_data_frames: FlexisDataFrames):
        process_time_data = flexis_data_frames.ProcessTime.to_dict(orient="index")
        process_time_list = []
        for entry, entry_values in process_time_data.items():
            for key in entry_values:
                if ":" in key:
                    new_key = key.split(":")[0]
                    process_time_data[entry][new_key] = process_time_data[entry].pop(key)
            process_time_list.append(ProcessTime(**process_time_data[entry]))
            
        # ProcessTime(**process_time_data[0])
        


    def write_data(self, file_path: str):
        pass

    # def read_data(self, file_path: str):
    #     data = load_json(file_path=file_path)
    #     self.seed = data["seed"]
    #     self.time_model_data = self.create_objects_from_configuration_data(
    #         data["time_models"], time_model_data.TIME_MODEL_DATA
    #     )
    #     self.state_data = self.create_objects_from_configuration_data(
    #         data["states"], state_data.STATE_DATA_UNION
    #     )
    #     self.process_data = self.create_objects_from_configuration_data(
    #         data["processes"], processes_data.PROCESS_DATA_UNION
    #     )

    #     self.queue_data = self.create_objects_from_configuration_data(data["queues"], queue_data.QueueData)
    #     self.resource_data = self.create_objects_from_configuration_data(data["resources"], resource_data.RESOURCE_DATA_UNION)
    #     self.material_data = self.create_objects_from_configuration_data(data["materials"], material_data.MaterialData)
    #     self.sink_data = self.create_objects_from_configuration_data(data["sinks"], sink_data.SinkData)
    #     self.source_data = self.create_objects_from_configuration_data(data["sources"], source_data.SourceData)

    # def create_typed_object_from_configuration_data(
    #     self, configuration_data: Dict[str, Any], type
    # ):
    #     objects = []
    #     for cls_name, items in configuration_data.items():
    #         for values in items.values():
    #             values.update({"type": cls_name})
    #             objects.append(parse_obj_as(type, values))
    #     return objects

    # def create_objects_from_configuration_data(
    #     self, configuration_data: Dict[str, Any], type
    # ):
    #     objects = []
    #     for values in configuration_data.values():
    #         objects.append(parse_obj_as(type, values))
    #     return objects

    # def write_data(self, file_path: str):
    #     data = self.get_dict_object_of_adapter()
    #     with open(file_path, "w") as json_file:
    #         json.dump(data, json_file)

    # def get_dict_object_of_adapter(self) -> dict:
    #     data = {
    #             "seed": self.seed,
    #             "time_models": self.get_dict_of_list_objects(self.time_model_data),
    #             "states": self.get_dict_of_list_objects(self.state_data),
    #             "processes": self.get_dict_of_list_objects(self.process_data),
    #             "queues": self.get_dict_of_list_objects(self.queue_data),
    #             "resources": self.get_dict_of_list_objects(self.resource_data),
    #             "materials": self.get_dict_of_list_objects(self.material_data),
    #             "sinks": self.get_dict_of_list_objects(self.sink_data),
    #             "sources": self.get_dict_of_list_objects(self.source_data)
    #     }
    #     return data

    # def get_dict_of_list_objects(self, values: List[BaseModel]) -> dict:
    #     return {counter: data.dict() for counter, data in enumerate(values)}
