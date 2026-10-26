class LamportClock:
    def __init__(self):
        self.time = 0

    def increment(self):
        self.time += 1

    def update(self, received_timestamp):
        self.time = max(self.time, received_timestamp) + 1

    def get_time(self):
        return self.time
