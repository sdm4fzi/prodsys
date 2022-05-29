processes = [3, 2, 1]
next_process: int = processes.pop()


def set_next_process(processes):
    # TODO: this method has also to be adjusted for the process model
    global next_process
    if not processes:
        next_process = None
    else:
        next_process = processes.pop()


while next_process:
    print(next_process)
    set_next_process(processes)