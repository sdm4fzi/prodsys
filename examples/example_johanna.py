from __future__ import annotations

import prodsys

#import pdfkit
from prodsys.util import kpi_visualization, runner
import os
import plotly.io as pio
#from fpdf import FPDF
import plotly.io as pio

import html2image

hti = html2image.Html2Image()



if __name__ == '__main__':

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()

    adapter_object.read_data('examples/hexagon_production_system.json')

    runner_object = prodsys.runner.Runner(adapter=adapter_object)

    #print(type(adapter_object.queue_data))

    runner_object.initialize_simulation()

    #print(runner_object.adapter.process_data)

    runner_object.run(600)
    

    #runner_object.print_results()

    #runner_object.save_results_as_csv("examples/tutorials/example_data/results.csv")
    #runner_object.plot_results()

    #runner_object.save_results_as_csv()
    post_processor = runner_object.get_post_processor()
    #runner_object.save_results_as_csv("examples/tutorials/example_data/results.csv")

    #report = kpi_visualization.generate_html_report(post_processor)

    # kpi_visualization.plot_time_per_state_of_resources(post_processor)
    kpi_visualization.plot_WIP_per_resource(post_processor) #graph make no sense
    # kpi_visualization.plot_throughput_time_over_time(post_processor) #graph is empty
    #kpi_visualization.plot_throughput_time_distribution(post_processor) #error because hist_data is empty
    # kpi_visualization.plot_boxplot_resource_utilization(post_processor) #graph is mostly empty
    #kpi_visualization.plot_line_balance_kpis(post_processor) #error because data contains NaN
    # kpi_visualization.plot_oee(post_processor) #error: Column not found: Percentage
    #kpi_visualization.plot_production_flow_rate_per_product(post_processor) #error: cant access "end_state"
    # kpi_visualization.plot_util_WIP_resource(post_processor) #error: Mean_WIP does not exist
    # #kpi_visualization.plot_transport_utilization_over_time(post_processor) #graph is empty
    # kpi_visualization.plot_WIP(post_processor)
    # kpi_visualization.plot_WIP_with_range(post_processor)


    
    