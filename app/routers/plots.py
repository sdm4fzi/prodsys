from typing import List


from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
import os

from prodsys.util import kpi_visualization
from prodsys import runner
from app.dependencies import prodsys_backend


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/plots",
    tags=["plots"],
    responses={404: {"description": "Not found"}},
)

@router.get("/throughput_time_distribution")
async def get_throughput_time_distribution(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_throughput_time_distribution(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/line_balance_kpis")
async def get_line_balance_kpis(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_line_balance_kpis(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/oee")
async def get_oee(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_oee(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/production_flow_rate_per_product")
async def get_production_flow_rate_per_product(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_production_flow_rate_per_product(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resource_utilization")
async def get_resource_utilization(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_boxplot_resource_utilization(post_processor, return_html=True)
        return HTMLResponse(content=html_content, media_type="text/html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/throughput_time_over_time")
async def get_throughput_time_over_time(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_throughput_time_over_time(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/time_per_state_of_resources")
async def get_time_per_state_of_resources(
    project_id: str,
    adapter_id: str,
    normalized: bool = True,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_time_per_state_of_resources(post_processor, normalized=normalized, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/util_WIP_resource")
async def get_util_WIP_resource(
    project_id: str,
    adapter_id: str,
    normalized: bool = True,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_util_WIP_resource(post_processor, normalized=normalized, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transport_utilization_over_time")
async def get_transport_utilization_over_time(
    project_id: str,
    adapter_id: str,
    transport_resource_names: List[str],
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_transport_utilization_over_time(post_processor, transport_resource_names=transport_resource_names, return_html=True)
        return HTMLResponse(content=html_content, media_type="text/html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/WIP_with_range")
async def get_WIP_with_range(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_WIP_with_range(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/WIP")
async def get_WIP(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_WIP(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/WIP_per_resource")
async def get_WIP_per_resource(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_WIP_per_resource(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/auxiliary_WIP")
async def get_auxiliary_WIP(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.plot_auxiliary_WIP(post_processor, return_html=True)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))