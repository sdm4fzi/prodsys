from pydantic import BaseModel


class ProgressReport(BaseModel):
    """
    Progress report of a task.

    Args:
        time_done (float): The time that is already done in seconds.
        expected_time_left (float): The expected time left to finish the task in seconds.
        expected_total_time (float): The expected total time to finish the task in seconds.
        ratio_done (float): The ratio of the task that is done.
    """
    ratio_done: float
    time_done: float
    expected_time_left: float
    expected_total_time: float

    