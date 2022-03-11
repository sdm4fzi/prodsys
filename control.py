import simpy


class Controler:
    def __init__(self, env):
        self.env = env
        self.control = env.process(self.control())



    def control_process(self):
        pass