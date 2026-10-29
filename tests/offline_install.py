"""Container integration test; execute with Docker --network none."""
import pathlib
import subprocess
import sys
import time
import urllib.request
import venv
import os

target = sys.argv[1] if len(sys.argv) > 1 else 'rhel87-cp312'
cache = pathlib.Path('/opt/seed/runtime-cache/tiktoken')
if cache.exists():
    os.environ['TIKTOKEN_CACHE_DIR'] = str(cache)
server = subprocess.Popen([sys.executable, '/opt/repo.py', 'serve'])
try:
    for attempt in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError('Service did not become ready')
    urllib.request.urlretrieve(f'http://127.0.0.1:8080/{target}/requirements.txt', '/tmp/requirements.txt')
    venv.create('/tmp/client', with_pip=True)
    python = '/tmp/client/bin/python'
    subprocess.run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir',
                    '--require-hashes', '--only-binary=:all:', '--index-url',
                    f'http://127.0.0.1:8080/{target}/simple/', '-r', '/tmp/requirements.txt'], check=True)
    subprocess.run([python, '-m', 'pip', 'check'], check=True)
    subprocess.run([python, str(pathlib.Path(__file__).with_name('smoke.py'))], check=True)
finally:
    server.terminate()
    server.wait(timeout=10)
