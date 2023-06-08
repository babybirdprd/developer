import sys
import os
import modal
import ast
import time  # Import time for sleep function

stub = modal.Stub("smol-developer-v1")
generatedDir = "generated"
openai_image = modal.Image.debian_slim().pip_install("openai", "tiktoken")
openai_model = "gpt-4" # or 'gpt-3.5-turbo',
openai_model_max_tokens = 2000 # i wonder how to tweak this properly

@stub.function(
    image=openai_image,
    secret=modal.Secret.from_dotenv(),
    retries=modal.Retries(
        max_retries=3,
        backoff_coefficient=2.0,
        initial_delay=1.0,
    ),
)
def generate_response(system_prompt, user_prompt, *args):
    import openai
    import tiktoken

    def reportTokens(prompt):
        encoding = tiktoken.encoding_for_model(openai_model)
        print("\033[37m" + str(len(encoding.encode(prompt))) + " tokens\033[0m" + " in prompt: " + "\033[92m" + prompt[:50] + "\033[0m")

    openai.api_key = os.environ["OPENAI_API_KEY"]

    messages = []
    messages.append({"role": "system", "content": system_prompt})
    reportTokens(system_prompt)
    messages.append({"role": "user", "content": user_prompt})
    reportTokens(user_prompt)
    role = "assistant"
    for value in args:
        messages.append({"role": role, "content": value})
        reportTokens(value)
        role = "user" if role == "assistant" else "assistant"

    params = {
        "model": openai_model,
        "messages": messages,
        "max_tokens": openai_model_max_tokens,
        "temperature": 0,
    }

    response = openai.ChatCompletion.create(**params)
    time.sleep(1)  # Add a delay of 1 second between API calls
    reply = response.choices[0]["message"]["content"]
    return reply


@stub.function()
def generate_file(filename, filepaths_string=None, shared_dependencies=None, prompt=None):
    # call openai api with this prompt
    filecode = generate_response.call(
        f"""You are an AI developer who specializes in generating TypeScript code for Next.js applications based on user intent.

    Given the following details:
    - App Intent: {prompt}
    - Filepaths: {filepaths_string}
    - Shared Dependencies: {shared_dependencies}

    Please generate valid TypeScript code for the specific file {filename}. Make sure to follow the given shared dependencies and ensure consistency in filenames if they are referenced. Do not include code fences or unnecessary explanation, simply return the necessary TypeScript code.
    """,
        f"""
    We have decided to split the program generation into separate files. Now, your task is to generate the TypeScript code for the file {filename}, ensuring it aligns with the shared dependencies and serves the purpose of the app which is {prompt}. Please start writing the code.
    """,
    )

    return filename, filecode


@stub.local_entrypoint()
def main(prompt, directory=generatedDir, file=None):
    # read file from prompt if it ends in a .md filetype
    if prompt.endswith(".md"):
        with open(prompt, "r") as promptfile:
            prompt = promptfile.read()

    print("hi its me, 🐣the smol developer🐣! you said you wanted:")
    # print the prompt in green color
    print("\033[92m" + prompt + "\033[0m")

    # call openai api with this prompt
    filepaths_string = generate_response.call(
        """You are an AI developer who specializes in creating Next.js applications with TypeScript.
        
    Given the user's intent of creating: {prompt}

    Please provide a list of filepaths that would be necessary to build such an application. Return this list as a python list of strings, with no additional explanations.
    """,
        prompt,
    )
    print(filepaths_string)
    # parse the result into a python list
    list_actual = []
    try:
        list_actual = ast.literal_eval(filepaths_string)

        # if shared_dependencies.md is there, read it in, else set it to None
        shared_dependencies = None
        if os.path.exists("shared_dependencies.md"):
            with open("shared_dependencies.md", "r") as shared_dependencies_file:
                shared_dependencies = shared_dependencies_file.read()

        if file is not None:
            # check file
            print("file", file)
            filename, filecode = generate_file(file, filepaths_string=filepaths_string, shared_dependencies=shared_dependencies, prompt=prompt)
            write_file(filename, filecode, directory)
        else:
            clean_dir(directory)

            # understand shared dependencies
            shared_dependencies = generate_response.call(
                """You are an AI developer who specializes in creating Next.js applications with TypeScript.
                
            In response to the user's prompt:

            ---
            the app is: {prompt}
            ---
            
            the files we have decided to generate are: {filepaths_string}

            Now, let's determine the shared dependencies among these files. These may include imported libraries, exported variables, DOM element IDs used by JavaScript functions, message names, function names, and TypeScript types.

            Kindly list these shared dependencies and provide a brief description for each. Focus exclusively on the names of the shared dependencies, and avoid any other explanations.
            """,
                prompt,
            )
            print(shared_dependencies)
            # write shared dependencies as a md file inside the generated directory
            write_file("shared_dependencies.md", shared_dependencies, directory)
            
            # Existing for loop
            for filepath in list_actual:
                filename, filecode = generate_file.call(
                    filepath,
                    filepaths_string=filepaths_string,
                    shared_dependencies=shared_dependencies,
                    prompt=prompt
                )
                write_file(filename, filecode, directory)
                time.sleep(0.3)  # Add a delay here to ensure we don't exceed rate limits


    except ValueError:
        print("Failed to parse result: " + filepaths_string)


def write_file(filename, filecode, directory):
    # Output the filename in blue color
    print("\033[94m" + filename + "\033[0m")
    print(filecode)
    
    file_path = directory + "/" + filename
    dir = os.path.dirname(file_path)
    os.makedirs(dir, exist_ok=True)

    # Open the file in write mode
    with open(file_path, "w") as file:
        # Write content to the file
        file.write(filecode)


def clean_dir(directory):
    import shutil

    extensions_to_skip = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.tif', '.tiff']  # Add more extensions if needed

    # Check if the directory exists
    if os.path.exists(directory):
        # If it does, iterate over all files and directories
        for root, dirs, files in os.walk(directory):
            for file in files:
                _, extension = os.path.splitext(file)
                if extension not in extensions_to_skip:
                    os.remove(os.path.join(root, file))
    else:
        os.makedirs(directory, exist_ok=True)


def generate_file(filename, filepaths_string=None, shared_dependencies=None, prompt=None):
    # call openai api with this prompt
    filecode = generate_response.call(
        f"""You are an AI developer who is trying to write a Next.js application with TypeScript based on the user's intent.
        
    The app's purpose is: {prompt}

    The files we have decided to generate are: {filepaths_string}

    The shared dependencies (like filenames and variable names) we have decided on are: {shared_dependencies}
    
    Now, your task is to generate the code for the file {filename}. Ensure to have consistent filenames if you reference other files we are also generating.
    
    Remember to respect these three criteria: 
       - You are generating code for the file {filename}
       - Do not deviate from the names of the files and the shared dependencies we have decided on
       - MOST IMPORTANT OF ALL - the purpose of our app is {prompt} - every line of code you generate must be valid TypeScript code for a Next.js application

    Start generating the code now.

    """,
        f"""
    We have broken up the program into per-file generation. 
    Now your job is to generate only the code for the file {filename}. 
    Make sure to have consistent filenames if you reference other files we are also generating.
    
    Remember that you must obey 3 things: 
       - you are generating code for the file {filename}
       - do not stray from the names of the files and the shared dependencies we have decided on
       - MOST IMPORTANT OF ALL - the purpose of our app is {prompt} - every line of code you generate must be valid code. Do not include code fences in your response, for example
    
    Bad response:
    ```typescript
    console.log("hello world")
    ```
    
    Good response:
    console.log("hello world")
    
    Begin generating the code now.

    """,
    )

    return filename, filecode

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Next.js TypeScript application based on user's intent")
    parser.add_argument("prompt", help="User's intent")
    parser.add_argument("--files", nargs='+', help="Specific files to generate")
    parser.add_argument("--directory", default="generated", help="Directory to output generated files")

    args = parser.parse_args()

    try:
        if args.files:
            for file in args.files:
                main(args.prompt, directory=args.directory, file=file)
        else:
            main(args.prompt, directory=args.directory)
    except Exception as e:
        print("Something went wrong:")
        print(e)
        import traceback

        traceback.print_exc()
