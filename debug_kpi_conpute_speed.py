import time
import prodsys
import pandas as pd
from prodsys.util.post_processing import PostProcessor


if __name__ == "__main__":
    events_csv_path = "/Users/sebastianbehrendt/Documents/code/prodsys/data/Example ProductionSystem_20260410-185542.csv"

    adapter_object = prodsys.ProductionSystemData.read(
        "examples/modelling_and_simulation/simulation_example_data/example_configuration.json"
    )
    prodsys.set_logging("CRITICAL")

    df_raw = pd.read_csv(events_csv_path)
    print(f"Events CSV: {len(df_raw)} rows, {df_raw.columns.tolist()}")

    runner_object = prodsys.runner.Runner(production_system_data=adapter_object)

    t0 = time.perf_counter()
    runner_object.post_processor = PostProcessor(
        production_system_data=adapter_object,
        df_raw=df_raw,
        time_range=200000,
        warm_up_cutoff=False,
        cut_off_method=None,
    )
    t_ingest = time.perf_counter() - t0
    print(f"\n--- PostProcessor init (ingest) ---")
    print(f"  {t_ingest:.3f}s")

    t0 = time.perf_counter()
    runner_object.print_results()
    t_print = time.perf_counter() - t0
    print(f"\n--- print_results (KPI compute) ---")
    print(f"  {t_print:.3f}s")

    print(f"\n=== TOTALS ===")
    print(f"  Ingest:       {t_ingest:.3f}s")
    print(f"  KPI compute:  {t_print:.3f}s")
    print(f"  Total:        {t_ingest + t_print:.3f}s")
