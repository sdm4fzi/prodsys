import numpy as np

EL_COUNT = 24
EL_LENGTH = 0.62
GRID_SIZE = 0.62*4
length = round(EL_COUNT * EL_LENGTH, 2)
print(length)
num_grid = int(length / GRID_SIZE)
print(num_grid)
positions = grid_position = list(np.linspace(length / num_grid, length, num_grid))
all_positions = []
for x in positions:
    for y in [0] + positions:
        all_positions.append([round(x, 2), round(y, 2)])
print(all_positions)