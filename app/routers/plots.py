from typing import List


from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
import os

from prodsys.util import kpi_visualization
from prodsys import runner
from app.dependencies import prodsys_backend, get_post_processor


router = APIRouter(
    prefix="/projects/{project_id}/adapters/{adapter_id}/plots",
    tags=["plots"],
    responses={404: {"description": "Not found"}},
)

@router.get("/throughput_time_distribution", response_class=HTMLResponse)
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
    
@router.get("/line_balance_kpis", response_class=HTMLResponse)
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

@router.get("/oee", response_class=HTMLResponse)
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

@router.get("/production_flow_rate_per_product", response_class=HTMLResponse)
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

@router.get("/resource_utilization", response_class=HTMLResponse)
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

@router.get("/throughput_time_over_time", response_class=HTMLResponse)
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

@router.get("/time_per_state_of_resources", response_class=HTMLResponse)
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

@router.get("/util_WIP_resource", response_class=HTMLResponse)
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

@router.get("/transport_utilization_over_time", response_class=HTMLResponse)
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

@router.get("/WIP_with_range", response_class=HTMLResponse)
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

@router.get("/WIP", response_class=HTMLResponse)
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

@router.get("/WIP_per_resource", response_class=HTMLResponse)
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
    
@router.get("/generate_html_report", response_class=HTMLResponse)
async def generate_html_report(
    project_id: str,
    adapter_id: str,
):
    try:
        post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
        html_content = kpi_visualization.generate_html_report(post_processor)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# @router.get("/generate_report", response_class=FileResponse)
# async def generate_report(
#     project_id: str,
#     adapter_id: str,
# ):
#     try:
#         post_processor = prodsys_backend.get_post_processor(project_id, adapter_id)
#         report_path = kpi_visualization.generate_report(post_processor)
        
#         if os.path.exists(report_path):
#             return FileResponse(report_path, filename="simulation_report.pdf")
#         else:
#             raise HTTPException(status_code=500, detail="Report generation failed")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))