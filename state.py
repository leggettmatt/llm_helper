import click
from style import click_text, separator
import time
import datetime

def current_time():
    current_time = datetime.datetime.now()
    return current_time.strftime("%Y-%m-%d %H:%M:%S")

def wrap_time(s):
    return f"{current_time()}: {s}"

class LoggingDict(dict):
    def __init__(self, *args, **kwargs):
        self.update_history = []
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        old_state = self.copy()
        super().__setitem__(key, value)
        self.update_history.append(old_state)

class State:
    def __init__(self, initial_status, status_map, initial_state=None):
        self.status = initial_status
        self.status_history = []
        self.status_map = status_map
        if initial_state is None:
            initial_state = {}
        elif not isinstance(initial_state, dict):
            raise TypeError("initial_state must be a dictionary")
        self.state = LoggingDict(initial_state)
    
    @property
    def state_history(self):
        return self.state.update_history + [self.state]

    def update_status(self, new_status):
        if new_status not in self.status_map:
            raise ValueError(f"Unknown status: {new_status}")
        self.status_history.append(self.status)
        self.status = new_status
    
    def print(self, s, color=None):
        click.echo(click_text(wrap_time(s), color))
    
    def run(self):
        while self.status != 'end':
            self.print(f"Current status: {self.status}")
            start_time = time.time()
            self.status_map[self.status]()
            end_time = time.time()
            execution_time = end_time - start_time
            self.print(f"State execution time: {execution_time:.2f} seconds")
            separator()
            yield self.state

    def end(self):
        raise ValueError('State machine has reached end state.')
    
