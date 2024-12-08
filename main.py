import runpod

def handler(event):
    rp_input = event['input']
    print(rp_input)

    return

if __name__ == '__main__':
    runpod.serverless.start({"handler": handler})
