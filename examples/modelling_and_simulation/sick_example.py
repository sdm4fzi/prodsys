# sick_line_with_workers_and_links.py
"""
SICK Production Line Simulation Model
======================================

This model implements the SICK production line based on data from EKx_SKx_SplittedV24_sick_model_as_json.json

Key Mappings from SICK JSON:
----------------------------

1. STORAGE UNIT TYPES (how many products per carrier):
   - SuSingle: 1 product per unit
   - SuDouble: 2 products per unit  
   - SuTray: 4 products per unit

2. STORAGE ZONE TYPES (queue capacity in number of storage units):
   - SzSingle0: 0 units, SzSingle1: 1 unit, SzSingle10: 10 units
   - SzDouble1: 1 unit, SzDouble3: 3 units, SzDouble5: 5 units, SzDouble9: 9 units
   - SzTray1: 1 unit, SzTray7: 7 units

3. STATION CAPACITY CALCULATION:
   Capacity (in products) = storageZoneType.size × storageUnitType.size
   
   Example: WcOvenHotTest uses SzDouble9 (9 units) and SuDouble (2 products/unit)
   → Capacity = 9 × 2 = 18 products

4. INPUT/OUTPUT QUEUE CONFIGURATION:
   Each station has wipIn (input queue) and wipOut (output queue) with capacities:
   - virtual: capacity based on storage unit type (SuSingle=1, SuDouble=2, SuTray=4)
   - SzSingle1: 1 × 1 = 1 product
   - SzDouble1: 1 × 2 = 2 products
   - SzDouble3: 3 × 2 = 6 products
   - SzDouble5: 5 × 2 = 10 products
   - SzDouble9: 9 × 2 = 18 products
   - SzTray1: 1 × 4 = 4 products
   - SzTray7: 7 × 4 = 28 products
   
   Examples: 
   - WcGlueCaterpillar has wipIn:SzDouble1 (2) and wipOut:SzDouble1 (2)
   - WcAlignEc has wipIn:virtual with SuDouble (2) and wipOut:virtual with SuDouble (2)

5. LOT DEPENDENCIES:
   Based on PsTypes.lotSize field, which defines batch processing requirements:
   - PstOvenCover: lotSize=7 (processes 7 products at once)
   - PstBufferSlide: lotSize=5 (processes 5 products at once)
   - PstOvenAdjust: lotSize=5
   - PstOvenHotTest: lotSize=9
   - PstCooling: lotSize=3

6. PROCESS TIMING:
   Each PsType has automatedTime and workerTime (in seconds)
   - Manual processes require worker interaction (workerTime)
   - Automated processes run independently (automatedTime)
"""

import prodsys.express as psx
from prodsys.simulation import runner
from prodsys.models.port_data import PortInterfaceType
import math

# ----------------------
# Global timing (your rule: 26 + 6 = 32 s for all steps)
# ----------------------
T_ALL = 26 + 6  # seconds

# ----------------------
# Transport — link-based
# ----------------------
tm_link = psx.DistanceTimeModel(speed=1, reaction_time=1/60, ID="tm_link")  # like example
# General transport capability that both workers can provide
cap_transport = "human_like_transport"

# Helper function to rotate coordinates
def rotate_coords(x, y, angle_deg):
    """Rotate coordinates by angle in degrees"""
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a

# ----------------------
# Network nodes from SICK model (coordinates in meters)
# ----------------------
n101 = psx.Node([3.528, 1.762], "n101")
n102 = psx.Node([3.528, 2.463], "n102")
n103 = psx.Node([3.528, 3.360], "n103")
n105 = psx.Node([3.528, 4.249], "n105")
n106 = psx.Node([3.528, 4.900], "n106")
n107 = psx.Node([3.528, 5.561], "n107")
n108 = psx.Node([3.247, 6.250], "n108")
n109 = psx.Node([2.501, 6.772], "n109")
n110 = psx.Node([2.135, 6.347], "n110")
n111 = psx.Node([2.135, 5.348], "n111")
n112 = psx.Node([2.135, 4.368], "n112")
n113 = psx.Node([2.135, 3.622], "n113")
n114 = psx.Node([2.135, 2.740], "n114")
n115 = psx.Node([2.135, 1.160], "n115")

# Source and sink nodes
n_src = psx.Node([3.528, 0.800], "n_src")  # Before first station
n_sink = psx.Node([2.135, 0.600], "n_sink")  # After last station

# ----------------------
# STEP 1: Define workers with separate transport processes and links
# ----------------------
# Create separate batch transport dependencies for each worker to avoid ID conflicts
batch_transport_dependency_worker1 = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="batch_transport_dependency_worker1")
batch_transport_dependency_worker2 = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="batch_transport_dependency_worker2")

# Worker 1 transport process (covers from source to assembly)
ltp_worker1 = psx.LinkTransportProcess(time_model=tm_link, capability=cap_transport, ID="ltp_worker1", links=[], dependencies=[batch_transport_dependency_worker1])

# Worker 2 transport process (covers from cover to packaging)
ltp_worker2 = psx.LinkTransportProcess(time_model=tm_link, capability=cap_transport, ID="ltp_worker2", links=[], dependencies=[batch_transport_dependency_worker2])

workers_part1 = psx.Resource(processes=[ltp_worker1], location=[3.528, 1.500], capacity=2, ID="Workers_Part1")
workers_part2 = psx.Resource(processes=[ltp_worker2], location=[2.135, 4.000], capacity=3, ID="Workers_Part2")



# ----------------------
# Interaction points (operator zones) calculated from physical assets + opZone offsets
# ----------------------
# WcGlue6Point: location (4.268, 1.762), opZone (0, 0.600), orientation 90°
op_x, op_y = rotate_coords(0, 0.600, 90)
ip_glue6 = psx.Node([4.268 + op_x, 1.762 + op_y], "ip_glue6")

# WcSolderingEc: location (4.115, 2.452), opZone (0, 0.370), orientation 90°
op_x, op_y = rotate_coords(0, 0.370, 90)
ip_solder = psx.Node([4.115 + op_x, 2.452 + op_y], "ip_solder")

# WcAlignEc: location (4.160, 3.360), opZone (0, 0.430), orientation 90°
op_x, op_y = rotate_coords(0, 0.430, 90)
ip_align = psx.Node([4.160 + op_x, 3.360 + op_y], "ip_align")

# WcGlueCaterpillar: location (4.094, 4.249), opZone (0, 0.404), orientation 90°
op_x, op_y = rotate_coords(0, 0.404, 90)
ip_cater = psx.Node([4.094 + op_x, 4.249 + op_y], "ip_cater")

# WcAssemblyTorque: location (4.115, 4.900), opZone (0, 0.370), orientation 90°
op_x, op_y = rotate_coords(0, 0.370, 90)
ip_asm = psx.Node([4.115 + op_x, 4.900 + op_y], "ip_asm")

# WcGlueCover: location (4.311, 5.561), opZone (0, 0.554), orientation 90°
op_x, op_y = rotate_coords(0, 0.554, 90)
ip_cover = psx.Node([4.311 + op_x, 5.561 + op_y], "ip_cover")

# WcOven: location (3.862, 6.700), opZone (0, -0.540), orientation -54°
op_x, op_y = rotate_coords(0, -0.540, -54)
ip_oven = psx.Node([3.862 + op_x, 6.700 + op_y], "ip_oven")

# WcAdjust_01: location (2.501, 7.443), opZone (0, -0.475), orientation 0°
op_x, op_y = rotate_coords(0, -0.475, 0)
ip_adjust1 = psx.Node([2.501 + op_x, 7.443 + op_y], "ip_adjust1")

# WcAdjust_02: location (1.429, 6.347), opZone (0, -0.475), orientation 90°
op_x, op_y = rotate_coords(0, -0.475, 90)
ip_adjust2 = psx.Node([1.429 + op_x, 6.347 + op_y], "ip_adjust2")

# WcOvenHotTest: location (1.644, 5.348), opZone (0, -0.300), orientation 90°
op_x, op_y = rotate_coords(0, -0.300, 90)
ip_oven_hot = psx.Node([1.644 + op_x, 5.348 + op_y], "ip_oven_hot")

# WcHotTest: location (1.430, 4.368), opZone (0, -0.475), orientation 90°
op_x, op_y = rotate_coords(0, -0.475, 90)
ip_hot = psx.Node([1.430 + op_x, 4.368 + op_y], "ip_hot")

# WcCooling: location (1.625, 3.622), opZone (0, -0.280), orientation 90°
op_x, op_y = rotate_coords(0, -0.280, 90)
ip_cooling = psx.Node([1.625 + op_x, 3.622 + op_y], "ip_cooling")

# WcFinalTest: location (1.430, 2.740), opZone (0, -0.475), orientation 90°
op_x, op_y = rotate_coords(0, -0.475, 90)
ip_final = psx.Node([1.430 + op_x, 2.740 + op_y], "ip_final")

# WcPackaging: location (1.405, 1.160), opZone (0, -0.540), orientation 90°
op_x, op_y = rotate_coords(0, -0.540, 90)
ip_pack = psx.Node([1.405 + op_x, 1.160 + op_y], "ip_pack")

# ----------------------
# STEP 2: Define worker dependencies for station processes
# ----------------------
def worker_dep(part, ip_node, dep_id):
    pool = workers_part1 if part == 1 else workers_part2
    return psx.ResourceDependency(ID=dep_id, required_resource=pool, interaction_node=ip_node)


# ----------------------
# Processes (split into manual and automated parts based on timing data)
# ----------------------
def P_manual(id_, time_seconds, worker_id, ip_node):
    dep = worker_dep(worker_id, ip_node, f"dep_{id_}_worker")
    # TODO: make sure dependency requests are executed immediately, and njo 100 seconds delay is generated at first.
    return psx.ProductionProcess(psx.FunctionTimeModel("constant", time_seconds, ID=f"tm_{id_}_manual"), ID=f"{id_}_manual", dependencies=[dep])

def P_automated(id_, time_seconds):
    return psx.ProductionProcess(psx.FunctionTimeModel("constant", time_seconds, ID=f"tm_{id_}_auto"), ID=f"{id_}_auto")

# Glue6Point: 6s manual + 26s automated
pp_glue6_manual   = P_manual("PstGlue6Point", 6, 1, ip_glue6)
pp_glue6_auto     = P_automated("PstGlue6Point", 26)

# SolderingEc: 28.2s manual + 0s automated (using average for all types)
pp_solder_manual  = P_manual("PstSolderingEc", 28.2, 1, ip_solder)
# pp_solder_auto    = P_automated("PstSolderingEc", 0)

# AlignEcLoadProg: 8s manual + 16s automated
pp_align_load_manual = P_manual("PstAlignEcLoadProg", 8, 1, ip_align)
pp_align_load_auto   = P_automated("PstAlignEcLoadProg", 16)

# AlignEcFirstTrack: 20s manual + 24s automated
pp_align_track1_manual = P_manual("PstAlignEcFirstTrack", 20, 1, ip_align)
pp_align_track1_auto   = P_automated("PstAlignEcFirstTrack", 24)

# AlignEcSecondTrack: 14s manual + 70s automated
pp_align_track2_manual = P_manual("PstAlignEcSecondTrack", 14, 1, ip_align)
pp_align_track2_auto   = P_automated("PstAlignEcSecondTrack", 70)

# GlueCaterpillar: 3.8s manual + 80.2s automated
pp_glue_cater_manual = P_manual("PstGlueCaterpillar", 3.8, 1, ip_cater)
pp_glue_cater_auto   = P_automated("PstGlueCaterpillar", 80.2)

# ----------------------
# Storage Unit Type Sizes (from SICK JSON)
# ----------------------
# SuSingle = 1 product, SuDouble = 2 products, SuTray = 4 products

# ----------------------
# Lot dependencies based on storageUnitType
# ----------------------
# These define batching requirements for processes
# LotDependency should equal the storageUnitType: Single=1, Double=2, Tray=4
# Tool capacity = storageZoneType.size × storageUnitType.size (e.g., SzTray7 × SuTray = 7 × 4 = 28)
dep_lot_oven_cover  = psx.LotDependency(min_lot_size=1, max_lot_size=4, ID="dep_lot_ov_cov")  # SuTray (4 products)
dep_lot_oven_adjust = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="dep_lot_ov_adj") # SuDouble (2 products)
dep_lot_oven_hot    = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="dep_lot_ov_hot") # SuDouble (2 products)
dep_lot_cooling     = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="dep_lot_cool")   # SuDouble (2 products)
dep_lot_buffer      = psx.LotDependency(min_lot_size=1, max_lot_size=2, ID="dep_lot_buffer") # SuDouble (2 products)


# BufferSlide: 0s manual + 450s automated (lotSize=5, SuDouble)
# pp_buffer_slide_manual = P_manual("PstBufferSlide", 0)
pp_buffer_slide_auto   = psx.ProductionProcess(psx.FunctionTimeModel("constant", 450, ID="tm_PstBufferSlide_auto"), 
                                               ID="PstBufferSlide_auto", dependencies=[dep_lot_buffer])

# AssemblyTorque: 25.1s manual + 0s automated (using average for all types)
pp_assembly_torque_manual = P_manual("PstAssemblyTorque", 25.1, 2, ip_asm)
# pp_assembly_torque_auto   = P_automated("PstAssemblyTorque", 0)

# GlueCover: 8.5s manual + 18.5s automated (using average for all types)
pp_glue_cover_manual = P_manual("PstGlueCover", 8.5, 2, ip_cover)
pp_glue_cover_auto   = P_automated("PstGlueCover", 18.5)

# OvenCover: 1.5s manual + 2100s automated (lotSize=7, SuTray)
pp_oven_cover_manual = P_manual("PstOvenCover", 1.5, 2, ip_oven)
pp_oven_cover_auto   = psx.ProductionProcess(psx.FunctionTimeModel("constant", 2100, ID="tm_PstOvenCover_auto"), 
                                             ID="PstOvenCover_auto", dependencies=[dep_lot_oven_cover])

# OvenAdjust: 2.3s manual + 900s automated (lotSize=5, SuDouble)
pp_oven_adjust_manual = P_manual("PstOvenAdjust", 2.3, 2, ip_oven)
pp_oven_adjust_auto   = psx.ProductionProcess(psx.FunctionTimeModel("constant", 900, ID="tm_PstOvenAdjust_auto"), 
                                              ID="PstOvenAdjust_auto", dependencies=[dep_lot_oven_adjust])

# Adjust: 16.8s manual + 203.2s automated (using average for all types)
pp_adjust_manual  = P_manual("PstAdjust", 16.8, 2, ip_adjust1)
pp_adjust_auto    = P_automated("PstAdjust", 203.2)

# OvenHotTest: 3s manual + 900s automated (lotSize=9, SuDouble)
pp_oven_hot_manual = P_manual("PstOvenHotTest", 3, 2, ip_oven_hot)
pp_oven_hot_auto   = psx.ProductionProcess(psx.FunctionTimeModel("constant", 900, ID="tm_PstOvenHotTest_auto"), 
                                           ID="PstOvenHotTest_auto", dependencies=[dep_lot_oven_hot])

# HotTest: 16.8s manual + 122.2s automated (using average for all types)
pp_hot_test_manual = P_manual("PstHotTest", 16.8, 2, ip_hot)
pp_hot_test_auto   = P_automated("PstHotTest", 122.2)

# Cooling: 0s manual + 240s automated (lotSize=3, SuDouble)
# pp_cooling_manual = P_manual("PstCooling", 0)
pp_cooling_auto   = psx.ProductionProcess(psx.FunctionTimeModel("constant", 240, ID="tm_PstCooling_auto"), 
                                          ID="PstCooling_auto", dependencies=[dep_lot_cooling])

# FinalTest: 14.5s manual + 44.5s automated (using average for all types)
pp_final_test_manual = P_manual("PstFinalTest", 14.5, 2, ip_final)
pp_final_test_auto   = P_automated("PstFinalTest", 44.5)

# Packaging: 6.2s manual + 0s automated (using average for all types)
pp_packaging_manual = P_manual("PstPackaging", 6.2, 2, ip_pack)
# pp_packaging_auto   = P_automated("PstPackaging", 0)

# ----------------------
# STEP 3: Define station resources
# ----------------------
# Stations with actual physical coordinates from SICK model (in meters)
# Only manual processes have worker dependencies

def create_resource_with_queues(processes, location, capacity, id, ip_node, wip_in_capacity, wip_out_capacity):
    """
    Create a resource with explicit input and output queues.
    
    Args:
        processes: List of production processes
        location: Resource location [x, y]
        capacity: Work capacity (number of products being processed)
        id: Resource ID
        ip_node: Interaction point node
        wip_in_capacity: Input queue capacity (number of products)
        wip_out_capacity: Output queue capacity (number of products)
    """
    resource = psx.Resource(processes=processes, location=location, capacity=capacity, ID=id)
    
    # Create input queue
    input_queue = psx.Queue(
        ID=f"{id}_input",
        # capacity=wip_in_capacity if wip_in_capacity > 8 else 8,
        capacity=20,  # Fixed to 30 to resolve queue size issues (temporary fix)
        location=ip_node.location,
        interface_type=PortInterfaceType.INPUT
    )
    
    # Create output queue
    output_queue = psx.Queue(
        ID=f"{id}_output",
        # capacity=wip_out_capacity if wip_out_capacity > 8 else 8,
        capacity=20,  # Fixed to 30 to resolve queue size issues (temporary fix)
        location=ip_node.location,
        interface_type=PortInterfaceType.OUTPUT
    )
    
    resource.ports = [input_queue, output_queue]
    return resource

# Station capacities and queues calculated from SICK JSON:
# Capacity = storageZoneType.size × storageUnitType.size
# Queue sizes based on wipIn and wipOut storage zone types
# Storage zone capacity mappings:
#   - virtual = depends on storage unit type (SuSingle=1, SuDouble=2, SuTray=4)
#   - SzSingle1 = 1 × 1 (SuSingle) = 1 product
#   - SzDouble1 = 1 × 2 (SuDouble) = 2 products
#   - SzDouble3 = 3 × 2 (SuDouble) = 6 products
#   - SzDouble5 = 5 × 2 (SuDouble) = 10 products
#   - SzDouble9 = 9 × 2 (SuDouble) = 18 products
#   - SzTray1 = 1 × 4 (SuTray) = 4 products
#   - SzTray7 = 7 × 4 (SuTray) = 28 products

# WcGlue6Point: work:SzSingle1 (1), wipIn:virtual (1), wipOut:virtual (1)
r_glue6 = create_resource_with_queues(
    [pp_glue6_manual, pp_glue6_auto], [4.268, 1.762], 1, "WcGlue6Point", ip_glue6, 
    wip_in_capacity=2, wip_out_capacity=2
)

# WcSolderingEc: work:SzSingle1 (1), wipIn:virtual (1), wipOut:SzDouble1 (2)
r_solder = create_resource_with_queues(
    [pp_solder_manual], [4.115, 2.452], 1, "WcSolderingEc", ip_solder,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcAlignEc: work:SzDouble1 (2), wipIn:virtual (1), wipOut:virtual (1)
r_align = create_resource_with_queues(
    [pp_align_load_manual, pp_align_load_auto, pp_align_track1_manual, pp_align_track1_auto, 
     pp_align_track2_manual, pp_align_track2_auto], [4.160, 3.360], 2, "WcAlignEc", ip_align,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcGlueCaterpillar: work:SzSingle1 (1), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_cater = create_resource_with_queues(
    [pp_glue_cater_manual, pp_glue_cater_auto], [4.094, 4.249], 1, "WcGlueCaterpillar", ip_cater,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcAssemblyTorque: work1:SzDouble5 (10), work2:SzSingle1 (1), wipIn:virtual (2), wipOut:virtual (2)
# Combined capacity for both processes (buffer slide uses 10, assembly uses 1)
# Virtual zones use SuDouble (2) based on buffer slide process
r_asm = create_resource_with_queues(
    [pp_buffer_slide_auto, pp_assembly_torque_manual], [4.115, 4.900], 11, "WcAssemblyTorque", ip_asm,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcGlueCover: work:SzSingle1 (1), wipIn:SzSingle1 (1), wipOut:SzTray1 (4)
r_cover = create_resource_with_queues(
    [pp_glue_cover_manual, pp_glue_cover_auto], [4.311, 5.561], 1, "WcGlueCover", ip_cover,
    wip_in_capacity=2, wip_out_capacity=4
)

# WcOven cover: work1:SzTray7 (28), wipIn:SzTray7 (28), wipOut:SzDouble1 (2)
# Note: Offset slightly from base location to avoid duplicate location error
r_oven_cover = create_resource_with_queues(
    [pp_oven_cover_manual, pp_oven_cover_auto], [3.862, 6.700], 28, "WcOven", ip_oven,
    wip_in_capacity=28, wip_out_capacity=2
)

# WcOven adjust: work2:SzDouble5 (10), wipIn:SzTray7 (28), wipOut:SzDouble1 (2)
# Note: Offset slightly from cover oven to represent different process area, shares input with cover
r_oven_adjust = create_resource_with_queues(
    [pp_oven_adjust_manual, pp_oven_adjust_auto], [3.862, 6.705], 10, "WcOvenAdjust", ip_oven,
    wip_in_capacity=28, wip_out_capacity=2
)

# WcAdjust: work1:SzSingle1 (1), work2:SzSingle1 (1), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_adjust_1 = create_resource_with_queues(
    [pp_adjust_manual, pp_adjust_auto], [2.501, 7.443], 1, "WcAdjust_1", ip_adjust1,
    wip_in_capacity=2, wip_out_capacity=2
)
r_adjust_2 = create_resource_with_queues(
    [pp_adjust_manual, pp_adjust_auto], [1.429, 6.347], 1, "WcAdjust_2", ip_adjust2,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcOvenHotTest: work1:SzDouble9 (18), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_oven_hot = create_resource_with_queues(
    [pp_oven_hot_manual, pp_oven_hot_auto], [1.644, 5.348], 18, "WcOvenHotTest", ip_oven_hot,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcHotTest: work1:SzSingle1 (1), work2:SzSingle1 (1), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_hot_1 = create_resource_with_queues(
    [pp_hot_test_manual, pp_hot_test_auto], [1.430, 4.368], 1, "WcHotTest_1", ip_hot,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcCooling: work:SzDouble3 (6), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_cooling = create_resource_with_queues(
    [pp_cooling_auto], [1.625, 3.622], 6, "WcCooling", ip_cooling,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcFinalTest: work1:SzSingle1 (1), work2:SzSingle1 (1), wipIn:SzDouble1 (2), wipOut:SzDouble1 (2)
r_final_1 = create_resource_with_queues(
    [pp_final_test_manual, pp_final_test_auto], [1.430, 2.740], 1, "WcFinalTest_1", ip_final,
    wip_in_capacity=2, wip_out_capacity=2
)

# WcPackaging: work:SzSingle1 (1), wipIn:SzDouble1 (2), wipOut:SzSingle1 (1)
r_pack = create_resource_with_queues(
    [pp_packaging_manual], [1.405, 1.160], 1, "WcPackaging", ip_pack,
    wip_in_capacity=2, wip_out_capacity=2
)
# ----------------------
# Product + link transport
# ----------------------
# Product route - manual processes before automated processes for each station
product = psx.Product(
    process=[
        # Glue6Point: manual then automated
        pp_glue6_manual, pp_glue6_auto,
        # SolderingEc: manual then automated
        pp_solder_manual,
        # AlignEc: manual then automated for each step
        pp_align_load_manual, pp_align_load_auto,
        pp_align_track1_manual, pp_align_track1_auto,
        pp_align_track2_manual, pp_align_track2_auto,
        # GlueCaterpillar: manual then automated
        pp_glue_cater_manual, pp_glue_cater_auto,
        # Assembly: manual then automated for each step
        pp_buffer_slide_auto,
        pp_assembly_torque_manual,
        # GlueCover: manual then automated
        pp_glue_cover_manual, pp_glue_cover_auto,
        # Oven processes: manual then automated
        pp_oven_cover_manual, pp_oven_cover_auto,
        pp_oven_adjust_manual, pp_oven_adjust_auto,
        # Adjust: manual then automated (parallel stations available)
        pp_adjust_manual, pp_adjust_auto,
        # OvenHotTest: manual then automated
        pp_oven_hot_manual, pp_oven_hot_auto,
        # HotTest: manual then automated
        pp_hot_test_manual, pp_hot_test_auto,
        # Cooling: manual then automated
        pp_cooling_auto,
        # FinalTest: manual then automated
        pp_final_test_manual, pp_final_test_auto,
        # Packaging: manual then automated
        pp_packaging_manual,
    ],
    # We use a RequiredCapabilityProcess and back it with actual LinkTransportProcess resources
    # The product will be transported by different workers at different stages
    transport_process=psx.RequiredCapabilityProcess(capability=cap_transport, ID="rcp_transport"),
    ID="SICK_Product",
)

# Source/Sink placed at actual network endpoints
# TODO: 15000 Stück in 120 Stunden -> Zwischenankunftszeit: 28.8s
src = psx.Source(product=product,
                 time_model=psx.FunctionTimeModel("exponential",28.0, ID="tm_arrival"),
                 location=[3.528, 0.800], ID="Source")
sink = psx.Sink(product=product, location=[2.135, 0.600], ID="Sink")

# ----------------------
# STEP 4: Assign links to worker transport processes
# ----------------------
# Worker 1 links: covers from source to assembly (n_src to n106)
ltp_worker1_links = [
    # Main spine for Worker 1 area (source to assembly)
    [n_src, n101], [n101, n_src],
    [n101, n102], [n102, n101],
    [n102, n103], [n103, n102],
    [n103, n105], [n105, n103],
    [n105, n106], [n106, n105],
    # Links to interaction points in Worker 1 area (bidirectional)
    [n101, ip_glue6], [ip_glue6, n101],
    [n102, ip_solder], [ip_solder, n102],
    [n103, ip_align], [ip_align, n103],
    [n105, ip_cater], [ip_cater, n105],
    [n106, ip_asm], [ip_asm, n106],
    # Links to stations for product transport in Worker 1 area (bidirectional)
    [n101, r_glue6], [r_glue6, n101],
    [n102, r_solder], [r_solder, n102],
    [n103, r_align], [r_align, n103],
    [n105, r_cater], [r_cater, n105],
    [n106, r_asm], [r_asm, n106],
    # Source connection
    [src, n_src], [n_src, src],
]

# Worker 2 links: covers from assembly to packaging (n106 to n_sink)
ltp_worker2_links = [
    # Connection from assembly to cover (handoff from Worker 1 to Worker 2)
    [n106, n107], [n107, n106],
    # Main spine for Worker 2 area (cover to sink)
    [n107, n108], [n108, n107],
    [n108, n109], [n109, n108],
    [n109, n110], [n110, n109],
    [n110, n111], [n111, n110],
    [n111, n112], [n112, n111],
    [n112, n113], [n113, n112],
    [n113, n114], [n114, n113],
    [n114, n115], [n115, n114],
    [n115, n_sink], [n_sink, n115],
    # Links to interaction points in Worker 2 area (bidirectional)
    [n107, ip_cover], [ip_cover, n107],
    [n108, ip_oven], [ip_oven, n108],
    [n109, ip_adjust1], [ip_adjust1, n109],
    [n110, ip_adjust2], [ip_adjust2, n110],
    [n111, ip_oven_hot], [ip_oven_hot, n111],
    [n112, ip_hot], [ip_hot, n112],
    [n113, ip_cooling], [ip_cooling, n113],
    [n114, ip_final], [ip_final, n114],
    [n115, ip_pack], [ip_pack, n115],
    # Links to stations for product transport in Worker 2 area (bidirectional)
    # Assembly station (for handoff from Worker 1)
    [n106, r_asm], [r_asm, n106],
    [n106, ip_asm], [ip_asm, n106],
    # Cover and beyond
    [n107, r_cover], [r_cover, n107],
    [n108, r_oven_cover], [r_oven_cover, n108],
    [n108, r_oven_adjust], [r_oven_adjust, n108],
    [n109, r_adjust_1], [r_adjust_1, n109],
    [n110, r_adjust_2], [r_adjust_2, n110],
    [n111, r_oven_hot], [r_oven_hot, n111],
    [n112, r_hot_1], [r_hot_1, n112],
    [n113, r_cooling], [r_cooling, n113],
    [n114, r_final_1], [r_final_1, n114],
    [n115, r_pack], [r_pack, n115],
    # Sink connection
    [n_sink, sink], [sink, n_sink],
]

# Update the worker transport processes with their respective links using set_links()
ltp_worker1.set_links(ltp_worker1_links)
ltp_worker2.set_links(ltp_worker2_links)

# ----------------------
# Build & run
# ----------------------
resources = [
    # stations
    r_glue6, r_solder, r_align, r_cater, r_asm, r_cover, r_oven_cover, r_oven_adjust,
    r_adjust_1, r_adjust_2, r_oven_hot, r_hot_1, r_cooling, r_final_1, r_pack,
    # workers (they handle both manual processes and transport)
    workers_part1, workers_part2,
]
system = psx.ProductionSystem(resources=resources, sources=[src], sinks=[sink])

system.validate()
model = system.to_model()
model.conwip_number = 10
# model.conwip_number = 200
sim = runner.Runner(production_system_data=model)
sim.initialize_simulation()
sim.run(80 * 60 * 60)  # Run for 8 hours
sim.save_results_as_csv()
sim.save_results_as_json()
sim.print_results()
sim.plot_results()
