import time
import urllib.request

import runpod
import json
import requests
from pathlib import Path

# Path object of dir. where script is ran.
curr_dir = Path.cwd()
# ComfyUI workflow to be used in this script.
COMFY_WORKFLOW_FILE_NAME = "example_workflow-api.json"
# Host where API server is running.
COMFY_API_HOST = "127.0.0.1:8188"
# Max attempts to connect to host.
COMFY_API_MAX_ATTEMPTS = 10
# Max delay between attempts to connect to host.
COMFY_API_MAX_DELAY = 2

def get_history(prompt_id: str):
    """
    Retrieve the history given the prompt_id.

    args:
        prompt_id (str): The ID of the prompt of which to retrieve history.

    Returns:
        dict: The history of the prompt, containing all of the results.
    """
    with urllib.request.urlopen(f"http://{COMFY_API_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def queue_workflow(workflow: dict):
    """
    Queue workflow to be sent to and processed by the ComfyUI API server.

    args:
        workflow (dict): A dictionary containing the workflow to be processed.

    Returns:
        dict: JSON response from ComfyUI after sent.
    """
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"http://{COMFY_API_HOST}/prompt", data=data)

    print(urllib.request.urlopen(req).read())
    return json.loads(urllib.request.urlopen(req).read())


def check_server(url: str, attempts: int = 10, delay: int = 2):
    """
    Checks to see if the ComfyUI API server is live.

    Args:
        url (str): URL to check for server.
        attempts (int, optional): How many tries to reach server.
        delay (int, optional): Time between each attempt in ms.

    Returns:
         boolean: True if the server can be reached, otherwise false.
    """

    for i in range(attempts):
        print(f"Attempt {i}")

        try:
            server_res = requests.get(url)

            # If the status code is 200, the server is live and running.
            if server_res.status_code == 200:
                print(f"Success. ComfyUI API server is live and reachable.")
                return True
        except requests.RequestException as e:
            # If there is an exception, the server may not be ready yet.
            pass

        # Wait for delay before retrying.
        time.sleep(delay)

    # If we are getting a status code other than 200 and no exceptions, there is failed connection.
    print(f"Failed to connect to ComfyUI server at {url} after {attempts} attempts.")
    return False


def validate_job_input(job_input):
    """
    Validates the input for the job.

    Args:
        job_input (dict): Dictionary containing job information to validate.

    Returns:
         tuple: A tuple containing the validated data and an error message, if any.
                The structure is: (validated data, error message)
    """

    # Validate if job input is provided.
    if job_input is None:
        return None, "Job input is not provided."

    # Check if job input is a string and parse it into JSON.
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.decoder.JSONDecodeError:
            return None, "Job input is not valid JSON."

    # Validate workflow in job input.
    hf_lora = job_input["hf_lora"]
    hyperparams = job_input["hyperparams"]

    if hf_lora is None or hyperparams is None:
        return None, "Need to provide both hf_lora and hyperparams in the request."

    # Return validated data with no error.
    return {"hf_lora": hf_lora, "hyperparams": hyperparams}, None


def handler(job):
    job_input = job['input']

    # Make sure the job input is valid.
    validated_data, error = validate_job_input(job_input)
    if error:
        return {"error": error}

    print("Input data validated.")

    # Extract the validated data.
    hf_lora = validated_data["hf_lora"]
    hyperparams = validated_data["hyperparams"]

    # Check if ComfyUI API server is live.
    check_server(f"http://{COMFY_API_HOST}", COMFY_API_MAX_ATTEMPTS, COMFY_API_MAX_DELAY)

    # Grab the workflow and queue it.
    wf_path = curr_dir.joinpath("workflows", COMFY_WORKFLOW_FILE_NAME)
    with open(wf_path, "r") as wf_file:
        workflow = json.load(wf_file)

    try:
        queued_workflow = queue_workflow(workflow=workflow)
        prompt_id = queued_workflow["prompt_id"]

        print(f"Queued workflow with a returned ID of: {prompt_id}")
    except Exception as e:
        return {"error": f"Error queuing workflow: {str(e)}"}

    return "Breakpoint. Workflow successfully queued."

    # Poll for completion.
    current_retry = 0
    try:
        while current_retry < COMFY_API_MAX_ATTEMPTS:
            history = get_history(prompt_id=prompt_id)

            if prompt_id in history and history[prompt_id].get("outputs"):
                break
            else:
                time.sleep(COMFY_API_MAX_DELAY / 1000)
                current_retry += 1

        else:
            return {"error": f"Exceeded the maximum number of retries."}
    except Exception as e:
        return {"error": f"Error waiting for image generation: {str(e)}"}

    return

if __name__ == '__main__':
    runpod.serverless.start({"handler": handler})
