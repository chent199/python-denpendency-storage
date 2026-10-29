"""Online preparation only. Requires uv and pip; never runs package build scripts."""
import argparse
import hashlib
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from tokenizer_cache import populate

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(output, packages):
    output = pathlib.Path(output).resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new bundle directory')
    # Restrict input to index package names and extras. No arbitrary URLs or options.
    if not packages or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9_,.-]+\])?', p) for p in packages):
        raise ValueError('Use package names with optional extras, without version pins or URLs')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=output.parent) as temp:
        stage = pathlib.Path(temp) / 'bundle'
        stage.mkdir()
        source = pathlib.Path(temp) / 'requirements.in'
        source.write_text('\n'.join(packages) + '\n')
        targets = json.loads((ROOT / 'targets.json').read_text())
        for name, target in targets.items():
            dest = stage / name
            wheels = dest / 'wheels'
            wheels.mkdir(parents=True)
            lock = dest / 'requirements.txt'
            print(f'Resolving {name}', flush=True)
            subprocess.run(['uv', 'pip', 'compile', str(source), '--python-platform', target['platform'],
                            '--python-version', target['python'], '--only-binary', ':all:',
                            '--prerelease', 'disallow', '--resolution', 'highest', '--upgrade',
                            '--generate-hashes', '--no-header', '--no-annotate', '--no-python-downloads',
                            '--default-index', 'https://pypi.org/simple', '-o', str(lock)],
                           check=True, stdout=subprocess.DEVNULL)
            platforms = target.get('pip_platforms')
            if platforms is None:
                platforms = [f'manylinux_2_{i}_x86_64' for i in range(target['glibc'], 4, -1)]
                platforms += ['manylinux2014_x86_64', 'manylinux2010_x86_64', 'manylinux1_x86_64']
            cmd = [sys.executable, '-m', 'pip', '--isolated', 'download', '--index-url', 'https://pypi.org/simple',
                   '--no-deps', '--only-binary=:all:', '--require-hashes', '--implementation', 'cp',
                   '--python-version', target['python'], '--abi', target['abi'], '--abi', 'abi3', '--abi', 'none',
                   '-r', str(lock), '-d', str(wheels)]
            for platform in platforms:
                cmd.extend(['--platform', platform])
            subprocess.run(cmd, check=True)
            simple = dest / 'simple'
            simple.mkdir()
            projects = {}
            for wheel in sorted(wheels.glob('*.whl')):
                project = re.sub(r'[-_.]+', '-', wheel.name.split('-')[0]).lower()
                projects.setdefault(project, []).append(wheel)
            for project, files in projects.items():
                folder = simple / project
                folder.mkdir()
                links = [f'<a href="../../wheels/{html.escape(w.name)}#sha256={sha(w)}">{html.escape(w.name)}</a><br>' for w in files]
                (folder / 'index.html').write_text('<!doctype html>\n' + '\n'.join(links))
            (simple / 'index.html').write_text('<!doctype html>\n' + '\n'.join(f'<a href="{p}/">{p}</a><br>' for p in projects))
        populate(stage)
        manifest = {'schema': 1, 'roots': packages, 'targets': targets,
                    'files': {str(p.relative_to(stage)): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        stage.rename(output)
    print(f'Complete: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Online: resolve and download a full replacement bundle for all targets')
    parser.add_argument('--output', required=True)
    parser.add_argument('--previous', help='Previous bundle directory: retain its root packages while adding new ones')
    parser.add_argument('packages', nargs='+')
    args = parser.parse_args()
    packages = args.packages
    if args.previous:
        packages = sorted(set(packages) | set(json.loads((pathlib.Path(args.previous) / 'manifest.json').read_text())['roots']))
    prepare(args.output, packages)
