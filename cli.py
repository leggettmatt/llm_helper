import re
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
from llm import stream_messages, stream_prompt, calculate_cost

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_data_directory():
    home_directory = os.path.expanduser("~")
    data_directory = os.path.join(home_directory, ".llm_helper_data")
    if not os.path.exists(data_directory):
        os.makedirs(data_directory)
    return data_directory

def write_to_jsonl(data, folder, file_prefix):
    # Ensure the history folder exists
    fully_qualified_history = f"{get_data_directory()}/{folder}"
    Path(fully_qualified_history).mkdir(parents=True, exist_ok=True)

    # Find all JSON files in the folder
    json_files = [f for f in os.listdir(fully_qualified_history) if f.endswith(".jsonl")]

    # Iterate over each JSON file and check the file size
    found_file = False
    for json_file in json_files:
        file_path = os.path.join(fully_qualified_history, json_file)
        file_size = os.path.getsize(file_path)

        # If file size is less than 15 MB, append data to the file
        if file_size < 15 * 1024 * 1024:
            found_file = True
            with open(file_path, "a") as f:
                f.write(json.dumps(data) + "\n")
            break

    # If no matching file is found, create a new file and write the data to it
    if not found_file:
        new_file_path = os.path.join(fully_qualified_history, f"{file_prefix}{len(json_files)}.jsonl")
        with open(new_file_path, "w") as f:
            f.write(json.dumps(data) + "\n")

def write_to_history(data):
    write_to_jsonl(data, "history", "history_")

def read_history():
    fully_qualified_history = f"{get_data_directory()}/history"
    json_files = [f for f in os.listdir(fully_qualified_history) if f.endswith(".jsonl")]

    dfs = []
    for json_file in json_files:
        file_name = f'{fully_qualified_history}/{json_file}'
        df = pd.read_json(file_name, lines=True)
        df['file_name'] = json_file
        dfs.append(df)

    return pd.concat(dfs)

def sha256_hash(input_string):
    # Create a SHA-256 hash object
    sha256 = hashlib.sha256()

    # Update the hash object with the bytes of the input string
    sha256.update(input_string.encode('utf-8'))

    # Get the hexadecimal representation of the hash
    hash_output = sha256.hexdigest()

    return hash_output

# Function to replace variables with user input
def replace_variables(prompt):
    variables = re.findall(r'\[\[(.*?)\]\]', prompt)
    if not variables:
        return prompt, dict(), ''
    config_hash = sha256_hash(','.join(variables))
    history = read_history().sort_values('created_at', ascending=False)
    if 'config' in history.columns:
        history = history[history['config_hash'] == config_hash]
        if history['created_at'].count() > 0:
            config = history['config'].iloc[0]
            response = click.prompt(click_text(f"Found config for this prompt. Use it? (n/No to not use)", "red"), default='', show_default=False)
            if not (response.lower() == 'n' or response.lower() == 'no'):
                click.echo(click_text("Using config", "red"))
                for variable in variables:
                    prompt = prompt.replace(f"[[{variable}]]", config[variable])
                return prompt, config, config_hash
            else:
                click.echo(click_text("Not using config", "red"))
        else:
            click.echo(click_text("No config found", "red"))
    config = dict()
    for variable in variables:
        user_value = click.prompt(click_text(f"Enter value for {variable}. If outputs from file type 'file'.", "red"), show_default=False)
        if user_value == 'file':
            file_name = click.prompt(click_text(f"  What is the file name?", "red"), show_default=False)
            user_value = open(file_name, 'r').read()
        config[variable] = user_value
        # user_value = input(f"Enter value for {variable}: ")
        prompt = prompt.replace(f"[[{variable}]]", user_value)
    return prompt, config, config_hash

@click.command()
@click.argument('file_location', type=click.Path(exists=True))
@click.option('--model', default='gpt-4', help='Openai model name.')
@click.option('--temperature', type=float, default=0.7, help='Temperature for the model.')
@click.option('--stop', help='Early stop parameter.')
@click.option('--print_tokens', is_flag=True, help="Whether to print the prompt or not (default: False)")
def run(file_location, model, temperature, stop, print_tokens):
    clear_screen()
    file_location = os.path.abspath(file_location)
    enc = tiktoken.encoding_for_model(model)
    count_tokens = lambda s: len(enc.encode(s))
    try:
        prompt = open(file_location, 'r').read()
        raw_prompt = prompt
        prompt, config, config_hash = replace_variables(prompt)
        saved_data = {'file_location': file_location, 'prompt': prompt, 'raw_prompt': raw_prompt, 'config': config, 'config_hash': config_hash, 'model': model, 'temperature': temperature, 'type': 'single_prompt', 'created_at': datetime.utcnow().isoformat()}

        start_time = time.time()
        completion = ''
        for text in stream_prompt(prompt, model, config.values(), temperature, stop, print_tokens):
            completion += text
        saved_data['interrupted'] = False
        end_time = time.time()
    except KeyboardInterrupt:
        click.echo(click_text("Keyboard interrupt detected. Saving data...", "red"))
        saved_data['interrupted'] = True
        end_time = time.time()
    except Exception as e:
        click.echo(f"An error occurred: {e}")
        return
    saved_data['completion'] = completion
    prompt_tokens = count_tokens(prompt)
    completion_tokens = count_tokens(completion)
    cost = calculate_cost(prompt_tokens, completion_tokens, model)
    saved_data['cost'] = cost
    saved_data['tokens_processed'] = prompt_tokens + completion_tokens
    execution_time = end_time - start_time
    saved_data['execution_time'] = execution_time
    separator()
    click.echo(click_text(f"Cost: ${cost:.5f}", "red"))
    click.echo(click_text(f"Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}", "red"))
    click.echo(click_text(f"Total tokens processed: {prompt_tokens + completion_tokens}", "red"))
    click.echo(click_text(f"Execution time: {execution_time:.2f} seconds", "red"))
    write_to_history(saved_data)

def print_summary(saved_data):
    separator()
    click.echo(click_text(f"Cost: ${saved_data['cost']:.5f}", "red"))
    click.echo(click_text(f"Prompt tokens: {saved_data['prompt_tokens']}, Completion tokens: {saved_data['completion_tokens']}", "red"))
    click.echo(click_text(f"Total tokens processed: {saved_data['prompt_tokens'] + saved_data['completion_tokens']}", "red"))
    click.echo(click_text(f"Execution time: {saved_data['execution_time']:.2f} seconds", "red"))


@click.command()
@click.argument('file_location', type=click.Path(exists=True))
@click.option('--model', default='gpt-4', help='Openai model name.')
@click.option('--temperature', type=float, default=0.7, help='Temperature for the model.')
@click.option('--stop', help='Early stop parameter.')
@click.option('--print_tokens', is_flag=True, help="Whether to print the prompt or not (default: False)")
def chat(file_location, model, temperature, stop, print_tokens):
    clear_screen()
    file_location = os.path.abspath(file_location)
    enc = tiktoken.encoding_for_model(model)
    count_tokens = lambda s: len(enc.encode(s))
    full_data = []
    try:
        prompt = open(file_location, 'r').read()
        raw_prompt = prompt
        prompt, config, config_hash = replace_variables(prompt)
        messages = [{"role": "system", "content": prompt}]
        user_response = 'temp'
        while user_response:
            saved_data = {'file_location': file_location, 'prompt': prompt, 'raw_prompt': raw_prompt, 'config': config, 'config_hash': config_hash, 'model': model, 'temperature': temperature, 'type': 'chat', 'created_at': datetime.utcnow().isoformat()}
            start_time = time.time()
            completion = ''
            prompt_tokens = count_tokens(''.join([m['content'] for m in messages]))
            for text in stream_messages(messages, model, config.values(), temperature, stop, print_tokens):
                completion += text
            saved_data['completion'] = completion
            saved_data['interrupted'] = False
            messages.append({'role': 'assistant', 'content': completion})
            user_response = click.prompt(click_text(f"Response", "red"), default='', show_default=False)
            messages.append({'role': 'user', 'content': user_response})
            end_time = time.time()
            execution_time = end_time - start_time
            completion_tokens = count_tokens(completion)
            cost = calculate_cost(prompt_tokens, completion_tokens, model)
            saved_data['cost'] = cost
            saved_data['tokens_processed'] = prompt_tokens + completion_tokens
            saved_data['prompt_tokens'] = prompt_tokens
            saved_data['completion_tokens'] = completion_tokens
            saved_data['execution_time'] = execution_time
            full_data.append(saved_data)
            print_summary(saved_data)
    except KeyboardInterrupt:
        click.echo(click_text("Keyboard interrupt detected. Saving data...", "red"))
        saved_data['completion'] = completion
        saved_data['interrupted'] = saved_data.get('interrupted', True)
        end_time = time.time()
        execution_time = end_time - start_time
        completion_tokens = count_tokens(completion)
        cost = calculate_cost(prompt_tokens, completion_tokens, model)
        saved_data['prompt_tokens'] = prompt_tokens
        saved_data['completion_tokens'] = completion_tokens
        saved_data['cost'] = cost
        saved_data['tokens_processed'] = prompt_tokens + completion_tokens
        saved_data['execution_time'] = execution_time
        full_data.append(saved_data)
        print_summary(saved_data)
    except Exception as e:
        click.echo(f"An error occurred: {e}")
        raise e
    separator()
    for saved_data in full_data:
        write_to_history(saved_data)

@click.command()
@click.argument('number_of_files', type=int)
@click.option('--interrupted', is_flag=True, help="Whether to include interrupted commands or not (default: False)")
def tail(number_of_files, interrupted):
    clear_screen()
    df = read_history().sort_values('created_at', ascending=False)
    df = df[df['type'] == 'single_prompt']
    if not interrupted:
        df = df[df['interrupted'] == False]
    df = df.head(number_of_files).sort_values('created_at')

    current_file = ''
    for index, row in df.iterrows():
        if row['file_name'] != current_file:
            click.echo(click_text(f"File: {row['file_name']}", "red"))
            separator()
            current_file = row['file_name']
        click.echo(click_text(f"Prompt: {row['prompt']}", "green"))
        click.echo(click_text(f"Completion: {row['completion']}", "blue"))
        parameters = {key: value for key, value in row.items() if key not in ['prompt', 'completion', 'file_name']}
        click.echo(click_text(f"Parameters: {parameters}", "red"))
        separator()

@click.command()
@click.argument('number_of_files', type=int)
@click.option('--interrupted', is_flag=True, help="Whether to include interrupted commands or not (default: False)")
def list(number_of_files, interrupted):
    clear_screen()
    df = read_history().sort_values('created_at', ascending=False)
    df = df[df['type'].isin(['single_prompt', 'chat'])]
    df['padded_type'] = df['type'].apply(lambda x: {'chat': 'chat' + ' '* 9}.get(x, x))
    if not interrupted:
        df = df[df['interrupted'] == False]
    df = df.head(number_of_files).sort_values('created_at')

    current_file = ''
    for index, row in df.iterrows():
        click.echo(click_text(f"Created at: {row['created_at']}.\tRun mode: {row['padded_type']}\tFile: {row['file_location']}", "red"))

@click.group()
def cli():
    pass

cli.add_command(run)
cli.add_command(tail)
cli.add_command(chat)
cli.add_command(list)

def main():
    cli()

if __name__ == '__main__':
    main()