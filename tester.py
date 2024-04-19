from tqdm import tqdm
import time

pbar = tqdm(total=100)

for i in range(100):
    pbar.update(1)
    time.sleep(0.1)

    ration_done = pbar.n / pbar.total
    duration = time.time() - pbar.start_t
    total_time = duration / ration_done
    time_left = total_time - duration

    print(ration_done, round(duration,2), total_time, time_left)

