This is a collection of simple helper functions I use for developing language projects. Probably should be multiple independent repos.

# CLI
### Getting started
Copy the .env template and update it with your openai api key.

```
cp .env.template .env
```

Install the CLI.

```
pip install -e .
```

Write a prompt. Prompt files are simple text files that identify variables with the syntax `[[variable]]`. This is better than the basic python variable definition because for a lot of language projects it's useful to return the response as json and so the `{variable}` syntax can cause formatting issues.

Once you've written a prompt run this command:
```
llm_helper run path/to/prompt/file
```

This will then ask you for the variables in the prompt one at a time and afterwords will run the prompt against the OpenAI api. After it's run it stores all data about the completion in the folder:
```
~/.llm_helper_data
```

You can review old runs using some of the CLI commands:
```
# Lists the last N runs you performed
llm_helper list [number_of_files]

# Prints out a more detailed list of the last runs
llm_helper tail [number_of_files]
```

`llm_helper chat` is the same structure as `run` with the exception that after the run is done it enters into a chat experience that you can then reask new questions

# State
This is a simple base class that you can use to declare a set of language jobs that gives you the same printing functionality out of the box. The basic idea is you inherit from `State`, the state has a single `status` that is updated after every status method is executed and has a single `state` property that you can manipulate and update with your status methods. The job finishes when the status is `end`. It's easier to see a toy example:

```
from llm_helper.llm import render_and_run_prompt
from llm_helper.state import State

class TestState(State):
    def __init__(self):
        super().__init__(
            initial_status='birthday',
            status_map={
                'birthday': self.birthday,
                'end': self.end # you always need to declare this to make it work
            },
            initial_state={'received_birthday': False}
        )
    
    def birthday(self):
        render_and_run_prompt("prompts/test.prompt", variables={'individual': 'Harrison Ford'})
        self.state['received_birthday'] = True
        self.update_status('end')
    
if __name__ == '__main__':
    test_state = TestState()
    test_state.run()
```

The `State` object logs status history in the `status_history` property and the state history in the `state_history` property for you by default.