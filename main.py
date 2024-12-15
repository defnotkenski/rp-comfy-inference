import os
from huggingface_hub import HfApi
import time
import runpod
import json
import requests
from pathlib import Path

hf_api = HfApi(token=os.environ["HF_TOKEN"])

# Repo in HuggingFace to upload outputs to.
HF_REPO_UPLOAD = "notkenski/inferences"
# Path object of dir. where script is ran.
curr_dir = Path.cwd()
# ComfyUI workflow to be used in this script.
COMFY_WORKFLOW_FILE_NAME = "example_workflow-api.json"
# Host where API server is running.
COMFY_API_HOST = "127.0.0.1:8188"
# Max attempts to connect to host.
COMFY_API_MAX_ATTEMPTS = 100
# Max delay between attempts to connect to host.
COMFY_API_MAX_DELAY = 5
# Output path for ComfyUI images.
COMFY_OUTPUT_PATH = Path("comfyui") / "output"

def mutate_workflow(hyperparams: dict, lora: str = ""):
    """
    Mutates the original workflow template and returns a modified dict.
    """
    wf_path = curr_dir.joinpath("workflows", COMFY_WORKFLOW_FILE_NAME)

    with open(wf_path, "r") as wf_file:
        parsed_workflow = json.load(wf_file)

        original_seed = parsed_workflow["25"]["inputs"]["noise_seed"]
        print(f"✨ Original seed: {original_seed}")

    # Mutate seed.
    parsed_workflow["25"]["inputs"]["noise_seed"] = hyperparams["noise_seed"]

    modified_seed = parsed_workflow["25"]["inputs"]["noise_seed"]
    print(f"✨ Modified seed: {modified_seed}")

    return parsed_workflow


def process_output_images(outputs: dict):
    """
    Grab the outputs and determine how to process the image for return.

    args:
        todo.

    returns:
        todo.
    """
    output_images = ""

    for node_id, node_output in outputs.items():
        # print(f"✨ {node_id}, {node_output}")

        if "images" in node_output:
            for image in node_output["images"]:
                output_images = Path(image["subfolder"]) / image["filename"]

    local_images_path = COMFY_OUTPUT_PATH / output_images
    print(f"✨ Local images path: {local_images_path}")

    if local_images_path.exists():
        try:
            hf_api.upload_file(
                path_or_fileobj=local_images_path,
                path_in_repo=local_images_path.name,
                repo_id=HF_REPO_UPLOAD
            )
            print(f"🦖 Successfully uploaded to HuggingFace.")

            return {"status": "success", "message": f"Successfully uploaded output to HuggingFace."}
        except Exception as e:
            return {"status": "error", "message": f"Error uploading to HF: {e}"}

    else:
        print(f"🦖 The image does not exist in the output folder at: {local_images_path}")
        return {"status": "error", "message": f"The image does not exist in the output folder at: {local_images_path}"}


def get_history(prompt_id: str):
    """
    Retrieve the history given the prompt_id.

    args:
        prompt_id (str): The ID of the prompt of which to retrieve history.

    Returns:
        dict: The history of the prompt, containing all of the results.
    """
    # with urllib.request.urlopen(f"http://{COMFY_API_HOST}/history/{prompt_id}") as response:
    #     return json.loads(response.read())

    req = requests.get(f"http://{COMFY_API_HOST}/history/{prompt_id}")
    parsed_req = req.json()

    return parsed_req


def queue_workflow(workflow: dict):
    """
    Queue workflow to be sent to and processed by the ComfyUI API server.

    args:
        workflow (dict): A dictionary containing the workflow to be processed.

    Returns:
        dict: JSON response from ComfyUI after sent.
    """
    data = json.dumps({"prompt": workflow}).encode("utf-8")

    req = requests.post(f"http://{COMFY_API_HOST}/prompt", data=data)
    parsed_req = req.json()

    print(parsed_req)

    return parsed_req


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

    # ====== Make sure the job input is valid. ======

    validated_data, error = validate_job_input(job_input)
    if error:
        return {"error": error}

    print("✨ Input data validated.")

    # TODO later.
    hf_lora = validated_data["hf_lora"]
    hyperparams = validated_data["hyperparams"]

    # ====== Check if ComfyUI API server is live. ======

    check_server(f"http://{COMFY_API_HOST}", COMFY_API_MAX_ATTEMPTS, COMFY_API_MAX_DELAY)

    # ====== Grab the workflow and queue it. ======

    # wf_path = curr_dir.joinpath("workflows", COMFY_WORKFLOW_FILE_NAME)
    # with open(wf_path, "r") as wf_file:
    #     workflow = json.load(wf_file)

    modified_workflow = mutate_workflow(hyperparams=hyperparams, lora=hf_lora)

    try:
        queued_workflow = queue_workflow(workflow=modified_workflow)
        prompt_id = queued_workflow["prompt_id"]

        print(f"✨ Queued workflow with a returned ID of: {prompt_id}")
    except Exception as e:
        return {"status": "error", "message": f"Error queuing workflow: {str(e)}"}

    # ====== Poll for completion. ======

    current_retry = 0

    try:
        while current_retry < COMFY_API_MAX_ATTEMPTS:
            history = get_history(prompt_id=prompt_id)

            if prompt_id in history and history[prompt_id].get("outputs"):
                break
            else:
                time.sleep(COMFY_API_MAX_DELAY)
                current_retry += 1

        else:
            return {"status": "error", "message": f"Exceeded the maximum number of retries."}
    except Exception as e:
        return {"status": "error", "message": f"Error waiting for image generation: {str(e)}"}

    process_results = process_output_images(outputs=history[prompt_id].get("outputs"))

    job_results = {
        **process_results,
        "refresh_worker": True
    }

    return job_results

if __name__ == '__main__':
    runpod.serverless.start({"handler": handler})
