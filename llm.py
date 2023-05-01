import re
import openai
import sys
import os
import click
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import hashlib
import tiktoken
import time

from style import click_text, separator

from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')

openai.api_key = OPENAI_KEY

def diff_echo(base_string, match_strings, match_color='green', no_match_color='white'):
    current_pos = 0
    match_positions = []

    # Find all occurrences of short strings in the long string and store their positions
    for match_string in match_strings:
        start_pos = 0
        while True:
            start_pos = base_string.find(match_string, start_pos)
            if start_pos == -1:
                break
            match_positions.append((start_pos, start_pos + len(match_string)))
            start_pos += len(match_string)

    # Sort match_positions based on start_pos
    match_positions.sort()

    # Iterate through the base_string and print accordingly
    for start_pos, end_pos in match_positions:
        no_match_substr = base_string[current_pos:start_pos]
        match_substr = base_string[start_pos:end_pos]

        click.echo(click_text(no_match_substr, no_match_color), nl=False)
        click.echo(click_text(match_substr, match_color, bold=True), nl=False)

        current_pos = end_pos

    # Print the remaining part of the base_string with no_match_color
    no_match_substr = base_string[current_pos:]
    click.echo(click_text(no_match_substr, no_match_color), nl=False)
    click.echo()

def calculate_cost(prompt_tokens, completion_tokens, model):
    if model == 'gpt-4':
        cost = prompt_tokens * 0.03 / 1000 # https://help.openai.com/en/articles/7127956-how-much-does-gpt-4-cost
        cost += completion_tokens * 0.06 / 1000
        return cost
    elif model == 'gpt-3.5-turbo':
        return (prompt_tokens + completion_tokens) * 0.002 / 1000
    else:
        raise Exception(f"Unknown model: {model}")

def count_tokens(s, model):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(s))

def stream(messages, model, temperature=0.7, stop=None, print_tokens=False):
    # This is the rawer method that only streams output but does none of the metadata calculations
    # It should be used when you expect to interrupt the stream before it finishes
    if not stop:
        response_iterator = openai.ChatCompletion.create(
            model=model,
            temperature=temperature,
            messages=messages,
            stream=True
        )
    else:
        response_iterator = openai.ChatCompletion.create(
            model=model,
            temperature=temperature,
            stop=stop,
            messages=messages,
            stream=True
        )
    completion = ''
    color = "blue"
    for response in response_iterator:
        if print_tokens:
            color = {
                'blue': 'yellow',
                'yellow': 'green',
                'green': 'red',
                'red': 'magenta',
                'magenta': 'blue'
            }[color]
        if response['choices'][0]['delta'].get('content'):
            text = response['choices'][0]['delta']['content']
            if print_tokens:
                click.echo(click_text(text, bold=False, background=color), nl=False)
            else:
                click.echo(click_text(text, color, bold=False), nl=False)
            yield text

def stream_prompt(prompt, model, variables=[], temperature=0.7, stop=None, print_tokens=False):
    # This is the rawer method that only streams output but does none of the metadata calculations
    # It should be used when you expect to interrupt the stream before it finishes
    messages=[{"role": "system", "content": prompt}]
    separator()
    diff_echo(prompt, variables, match_color='red', no_match_color='green')
    yield from stream(messages, model, temperature, stop, print_tokens)
    click.echo()

def stream_messages(messages, model, variables=[], temperature=0.7, stop=None, print_tokens=False):
    # This is the rawer method that only streams output but does none of the metadata calculations
    # It should be used when you expect to interrupt the stream before it finishes
    separator()
    for i, message in enumerate(messages):
        if i == 0:
            diff_echo(message['content'], variables, match_color='red', no_match_color='green')
        else:
            color = {"user": "red", "system": "green", "assistant": "blue"}[message['role']]
            click.echo(click_text(f"{message['role']}: {message['content']}", color, bold=False))
    yield from stream(messages, model, temperature, stop, print_tokens)
    click.echo()

def run_prompt(prompt, model, substituted_variables=[], temperature=0.7, stop=None, print_tokens=False):
    start_time = time.time()
    completion = ''
    for text in stream_prompt(prompt, model, substituted_variables, temperature, stop, print_tokens):
        completion += text
    click.echo()
    end_time = time.time()
    execution_time = end_time - start_time
    prompt_tokens = count_tokens(prompt, model)
    completion_tokens = count_tokens(completion, model)
    cost = calculate_cost(prompt_tokens, completion_tokens, model)
    click.echo(click_text(f"Cost: ${cost:.5f}", "red"))
    click.echo(click_text(f"Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}", "red"))
    click.echo(click_text(f"Total tokens processed: {prompt_tokens + completion_tokens}", "red"))
    click.echo(click_text(f"Prompt execution time: {execution_time:.2f} seconds", "red"))
    separator()
    return completion


# Function to replace variables with user input
def replace_variables(prompt, config):
    variables = re.findall(r'\[\[(.*?)\]\]', prompt)
    for variable in variables:
        user_value = config[variable]
        prompt = prompt.replace(f"[[{variable}]]", user_value)
    return prompt

def render_and_run_prompt(prompt_location, model='gpt-4', variables=dict(), temperature=0.7, stop=None, print_tokens=False):
    prompt = open(prompt_location, 'r').read()
    prompt = replace_variables(prompt, variables)
    return run_prompt(prompt, model, variables.values(), temperature, stop, print_tokens)