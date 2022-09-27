from tqdm import tqdm
from time import sleep

pbar = tqdm(total=100)

for i in range(10):
    sleep(0.1)
    pbar.moveto(12.2)