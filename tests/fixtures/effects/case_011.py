import subprocess

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True)
