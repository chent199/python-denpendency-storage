"""Offline static index and atomic bundle import. No external dependencies."""
import argparse
import fcntl
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import tempfile
import uuid

DATA = pathlib.Path(os.environ.get('REPO_DATA', '/data'))


def verify(source):
    source = pathlib.Path(source).resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['schema'] != 1 or not manifest['files']:
        raise ValueError('Invalid manifest')
    expected = set(manifest['files']) | {'manifest.json'}
    actual = set()
    for p in source.rglob('*'):
        if p.is_symlink():
            raise ValueError('Symlinks are not allowed in bundles')
        if p.is_file():
            actual.add(p.relative_to(source).as_posix())
    if actual != expected:
        raise ValueError('Bundle file list mismatch')
    for name, digest in manifest['files'].items():
        relative = pathlib.PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid bundle path')
        with (source / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError(f'Checksum mismatch: {name}')
    return manifest


def publish(source):
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        generations = DATA / 'generations'
        generations.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=generations) as temp:
            stage = pathlib.Path(temp) / 'bundle'
            shutil.copytree(source, stage, symlinks=True)
            manifest = verify(stage)
            # Keep content-addressed wheel paths stable across updates for in-flight clients.
            for wheel in stage.glob('*/wheels/*.whl'):
                dest = DATA / wheel.relative_to(stage)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    if hashlib.sha256(dest.read_bytes()).digest() != hashlib.sha256(wheel.read_bytes()).digest():
                        raise ValueError(f'Wheel filename collision: {wheel.name}')
                else:
                    shutil.copy2(wheel, dest)
            ident = uuid.uuid4().hex
            stage.rename(generations / ident)
            pointer = DATA / ('.current-' + ident)
            pointer.symlink_to('generations/' + ident, target_is_directory=True)
            pointer.replace(DATA / 'current')
            for target in manifest['targets']:
                folder = DATA / target
                folder.mkdir(exist_ok=True)
                for name in ('simple', 'requirements.txt'):
                    link = folder / name
                    if not link.exists():
                        link.symlink_to(f'../current/{target}/{name}')
            cache_link = DATA / 'runtime-cache'
            if (DATA / 'current/runtime-cache').is_dir() and not cache_link.exists():
                cache_link.symlink_to('current/runtime-cache', target_is_directory=True)
    print('Published:', ', '.join(manifest['roots']), flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200 if (DATA / 'current').exists() else 503)
            self.end_headers()
            self.wfile.write(b'ok\n')
        elif self.path.startswith(('/generations', '/current', '/.')):
            self.send_error(404)
        else:
            super().do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('serve').add_argument('--port', type=int, default=8080)
    sub.add_parser('import').add_argument('directory')
    args = parser.parse_args()
    if args.command == 'import':
        publish(args.directory)
    else:
        if not (DATA / 'current').exists():
            publish('/opt/seed')
        os.chdir(DATA)
        http.server.ThreadingHTTPServer(('0.0.0.0', args.port), Handler).serve_forever()
