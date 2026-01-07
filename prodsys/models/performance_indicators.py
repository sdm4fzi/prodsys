from enum import Enum
from typing import Literal, List, Optional, Union, Tuple

from pydantic import BaseModel, ConfigDict, field_validator


class KPIEnum(str, Enum):
    """
    Enum that represents the different kind of KPIs.
    """

    OUTPUT = "output"
    THROUGHPUT = "throughput"
    COST = "cost"
    WIP = "WIP"
    PRIMITIVE_WIP = "primitive_WIP"

    TRHOUGHPUT_TIME = "throughput_time"
    PROCESSING_TIME = "processing_time"

    PRODUCTIVE_TIME = "productive_time"
    STANDBY_TIME = "standby_time"
    SETUP_TIME = "setup_time"
    CHARGING_TIME = "charging_time"
    UNSCHEDULED_DOWNTIME = "unscheduled_downtime"
    DEPENDENCY_TIME = "dependency_time"

    DYNAMIC_WIP = "dynamic_WIP"
    DYNAMIC_THROUGHPUT_TIME = "dynamic_throughput_time"


class KPILevelEnum(str, Enum):
    """
    Enum that represents the different kind of KPI levels.
    """

    SYSTEM = "system"
    RESOURCE = "resource"
    ALL_PRODUCTS = "all_products"
    PRODUCT_TYPE = "product_type"
    PRODUCT = "product"
    PROCESS = "process"


class KPI(BaseModel):
    """
    Class that represents a KPI. Not intended for usage but only inheritance.

    Args:
        name (KPIEnum): Name of the KPI.
        target (Literal["min", "max"]): Favourable target of the KPI.
        weight (Optional[float], optional): Weight of the KPI. Defaults to 1.
        value (Optional[float], optional): Value of the KPI. Defaults to None.
        context (Tuple[KPILevelEnum, ...], optional): Context of the KPI. Defaults to None.
        resource (Optional[str], optional): Resource of the KPI. Defaults to None.
        product_type (Optional[str], optional): Product type of the KPI. Defaults to None.    Returns:
    """

    name: KPIEnum
    target: Literal["min", "max"]
    weight: Optional[float] = 1
    value: Optional[float] = None
    context: Optional[Tuple[KPILevelEnum, ...]] = None
    resource: Optional[str] = None
    product_type: Optional[str] = None

    @field_validator("context", mode="before")
    def sort_context(cls, v):
        return tuple(sorted(v))


class DynamicKPI(KPI):
    """
    Class that represents a dynamic KPI. Not intended for usage but only inheritance.
    """

    start_time: float
    end_time: float
    product: Optional[str] = None
    process: Optional[str] = None


class Output(KPI):
    name: Literal[KPIEnum.OUTPUT] = KPIEnum.OUTPUT
    target: Literal["max"] = "max"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "output",
                    "target": "max",
                    "weight": 1,
                    "value": 34,
                    "context": ["system", "product_type"],
                    "product_type": "ProductType_1",
                }
            ]
        }
    )


class Throughput(KPI):
    name: Literal[KPIEnum.THROUGHPUT]
    target: Literal["max"] = "max"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "throughput",
                    "target": "max",
                    "weight": 1,
                    "value": 4.32,
                    "context": ["system", "product_type"],
                    "product_type": "ProductType_1",
                }
            ]
        }
    )


class Cost(KPI):
    name: Literal[KPIEnum.COST]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "cost",
                    "target": "min",
                    "weight": 0.5,
                    "value": 36000,
                    "context": ["system"],
                }
            ]
        }
    )


class WIP(KPI):
    name: Literal[KPIEnum.WIP]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "WIP",
                    "target": "min",
                    "weight": 1,
                    "value": 121,
                    "context": ["system", "product_type"],
                    "product_type": "ProductType_1",
                }
            ]
        }
    )


class PrimitiveWIP(KPI):
    name: Literal[KPIEnum.PRIMITIVE_WIP]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "PRIMITIVE_WIP",
                    "target": "min",
                    "weight": 1,
                    "value": 121,
                    "context": ["system", "product_type"],
                    "product_type": "Primitive_1",
                }
            ]
        }
    )


class DynamicWIP(DynamicKPI, WIP):
    name: Literal[KPIEnum.DYNAMIC_WIP]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "dynamic_WIP",
                    "target": "min",
                    "weight": 1,
                    "value": 121,
                    "context": ["system", "product"],
                    "product_type": "ProductType_1",
                    "start_time": 21.2,
                    "end_time": 23.4,
                }
            ]
        }
    )


class ThroughputTime(KPI):
    name: Literal[KPIEnum.TRHOUGHPUT_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "throughput_time",
                    "target": "min",
                    "weight": 1,
                    "value": 221.1,
                    "context": ["system", "product_type"],
                    "product_type": "ProductType_1",
                }
            ]
        }
    )


class DynamicThroughputTime(DynamicKPI, ThroughputTime):
    name: Literal[KPIEnum.DYNAMIC_THROUGHPUT_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "dynamic_throughput_time",
                    "target": "min",
                    "weight": 1,
                    "value": 221.1,
                    "context": ["system", "product"],
                    "product_type": "ProductType_1",
                    "product": "Product_1_23",
                    "start_time": 21.2,
                    "end_time": 23.4,
                }
            ]
        }
    )


class ProcessingTime(KPI):
    name: Literal[KPIEnum.PROCESSING_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "processing_time",
                    "target": "min",
                    "weight": 1,
                    "value": 1.2,
                    "context": ["resource", "process"],
                    "resource": "Resource_1",
                    "process": "P1",
                }
            ]
        }
    )


class ProductiveTime(KPI):
    name: Literal[KPIEnum.PRODUCTIVE_TIME]
    target: Literal["max"] = "max"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "productive_time",
                    "target": "max",
                    "weight": 1,
                    "value": 0.65,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


class StandbyTime(KPI):
    name: Literal[KPIEnum.STANDBY_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "standby_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.12,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


class SetupTime(KPI):
    name: Literal[KPIEnum.SETUP_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "setup_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.08,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


class ChargingTime(KPI):
    name: Literal[KPIEnum.CHARGING_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "charging_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.1,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


class UnscheduledDowntime(KPI):
    name: Literal[KPIEnum.UNSCHEDULED_DOWNTIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "unscheduled_downtime",
                    "target": "min",
                    "weight": 1,
                    "value": 0.1,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


class DependencyTime(KPI):
    name: Literal[KPIEnum.DEPENDENCY_TIME]
    target: Literal["min"] = "min"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "dependency_time",
                    "target": "min",
                    "weight": 1,
                    "value": 0.15,
                    "context": ["resource"],
                    "resource": "Resource_1",
                }
            ]
        }
    )


KPI_UNION = Union[
    Output,
    Throughput,
    Cost,
    WIP,
    ThroughputTime,
    ProcessingTime,
    ProductiveTime,
    StandbyTime,
    SetupTime,
    ChargingTime,
    UnscheduledDowntime,
    DependencyTime,
    DynamicWIP,
    DynamicThroughputTime,
]
