import time
import runpod
import json
import requests

# Host where API server is running.
COMFY_API_HOST = "127.0.0.1:8188"
# Max attempts to connect to host.
COMFY_API_MAX_ATTEMPTS = 500
# Max delay between attempts to connect to host.
COMFY_API_MAX_DELAY = 50

def check_server(url: str, attempts: int = 10, delay: int = 500):
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
        time.sleep(delay / 1000)

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
    workflow = job_input["workflow"]

    if workflow is None:
        return None, "Workflow is not provided."

    # Validate images in job input, if provided.
    images = job_input["images"]

    if images is not None:
        if not isinstance(images, list) or not all("name" in image and "image" in image for image in images):
            return None, "Images must be a list with the properties: name and image."

    # Return validated data with no error.
    return {"workflow": workflow, "images": images}, None


def handler(job):
    job_input = job['input']

    # Make sure the job input is valid.
    validated_data, error = validate_job_input(job_input)
    if error:
        return {"error": error}

    # Extract the validated data.
    workflow = validated_data["workflow"]
    images = validated_data["images"]

    # Check if ComfyUI API server is live.
    check_server(f"http:{COMFY_API_HOST}", COMFY_API_MAX_ATTEMPTS, COMFY_API_MAX_DELAY)

    return

if __name__ == '__main__':
    runpod.serverless.start({"handler": handler})
