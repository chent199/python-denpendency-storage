"""Run on the real target computer using its intended Python. No Internet required."""
import argparse
import json
import pathlib
import platform
import subprocess
import sys
import venv
import os

parser = argparse.ArgumentParser()
parser.add_argument('--target', required=True)
parser.add_argument('--bundle', type=pathlib.Path, required=True)
parser.add_argument('--venv', type=pathlib.Path, required=True)
args = parser.parse_args()
target = json.loads((args.bundle / 'manifest.json').read_text())['targets'][args.target]
cache = args.bundle.resolve() / 'runtime-cache/tiktoken'
if cache.exists():
    os.environ['TIKTOKEN_CACHE_DIR'] = str(cache)
if platform.python_implementation() != 'CPython' or platform.python_version() != target['python']:
    raise SystemExit(f"Use CPython {target['python']}; found {platform.python_implementation()} {platform.python_version()}")
if platform.machine().lower() not in ('amd64', 'x86_64') or sys.maxsize <= 2**32:
    raise SystemExit('Requires x86_64 / AMD64, 64-bit Python')
if ('windows' in target['platform']) != (sys.platform == 'win32'):
    raise SystemExit('Wrong operating system')
if 'glibc' in target:
    if sys.platform != 'linux':
        raise SystemExit('Requires Linux')
    name, version = platform.libc_ver()
    if name != 'glibc' or tuple(map(int, version.split('.')[:2])) < (2, target['glibc']):
        raise SystemExit(f"Requires glibc >= 2.{target['glibc']}; found {name} {version}")
if args.venv.exists():
    raise SystemExit('Choose a new venv path; existing environments are preserved')
venv.create(args.venv, with_pip=True)
python = args.venv / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
folder = args.bundle.resolve() / args.target
subprocess.run([str(python), '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                '--no-index', '--no-cache-dir', '--only-binary=:all:', '--require-hashes',
                '--find-links', str(folder / 'wheels'), '-r', str(folder / 'requirements.txt')], check=True)
subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
subprocess.run([str(python), str(pathlib.Path(__file__).resolve().parents[1] / 'tests/smoke.py')], check=True)
print('Target verification passed:', args.target)
