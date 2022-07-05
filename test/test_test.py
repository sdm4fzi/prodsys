processes = ["P1", "P2"]
quantities = [2, 3]

for process, q in zip(processes, quantities):
    processes += [process]*(q - 1)
    # for _ in range(q-1):
    #     processes.append(process)

print(processes)

