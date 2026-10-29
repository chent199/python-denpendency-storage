"""Fetch tokenizer assets using the hashes embedded in the selected tiktoken wheel."""
import argparse
import ast
import hashlib
import json
import pathlib
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile


def populate(bundle):
    bundle = pathlib.Path(bundle)
    wheels = list(bundle.glob('*/wheels/tiktoken-*.whl'))
    if not wheels:
        return
    assets = {}
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            tree = ast.parse(archive.read('tiktoken_ext/openai_public.py').decode())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            kw = {k.arg: k.value.value for k in node.keywords if isinstance(k.value, ast.Constant)}
            if node.func.id == 'load_tiktoken_bpe':
                assets[ast.literal_eval(node.args[0])] = kw['expected_hash']
            elif node.func.id == 'data_gym_to_mergeable_bpe_ranks':
                assets[kw['vocab_bpe_file']] = kw['vocab_bpe_hash']
                assets[kw['encoder_json_file']] = kw['encoder_json_hash']
    if not assets:
        raise ValueError('No known tokenizer assets; inspect new tiktoken format')
    with tempfile.TemporaryDirectory(dir=bundle.parent) as tmp:
        cache = pathlib.Path(tmp) / 'tiktoken'
        cache.mkdir()
        for url, expected in assets.items():
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'openaipublic.blob.core.windows.net' or not re.fullmatch('[a-f0-9]{64}', expected):
                raise ValueError('Unexpected tokenizer asset source or hash')
            print('Downloading tokenizer:', url, flush=True)
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Tokenizer checksum mismatch: ' + url)
            (cache / hashlib.sha1(url.encode()).hexdigest()).write_bytes(data)
        dest = bundle / 'runtime-cache/tiktoken'
        dest.parent.mkdir(exist_ok=True)
        shutil.copytree(cache, dest, dirs_exist_ok=True)
    print('Tokenizer cache verified:', len(assets), 'assets')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=pathlib.Path)
    args = parser.parse_args()
    populate(args.bundle)
    path = args.bundle / 'manifest.json'
    manifest = json.loads(path.read_text())
    for file in (args.bundle / 'runtime-cache').rglob('*'):
        if file.is_file():
            manifest['files'][file.relative_to(args.bundle).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest, indent=2) + '\n')
