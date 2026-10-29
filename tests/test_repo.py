import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('repo', pathlib.Path(__file__).resolve().parents[1] / 'tools/repo.py')
repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo)


class PublishTest(unittest.TestCase):
    def test_atomic_update_integrity_and_stable_wheels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo.DATA = root / 'data'
            bundle = root / 'bundle'
            (bundle / 'test/wheels').mkdir(parents=True)
            (bundle / 'test/simple/pkg').mkdir(parents=True)
            wheel = bundle / 'test/wheels/pkg-1-py3-none-any.whl'
            wheel.write_bytes(b'initial')
            index = bundle / 'test/simple/pkg/index.html'
            index.write_text('initial index')
            (bundle / 'test/requirements.txt').write_text('pkg==1\n')
            (bundle / 'runtime-cache/tiktoken').mkdir(parents=True)
            (bundle / 'runtime-cache/tiktoken/test-cache').write_bytes(b'vocabulary')

            def manifest():
                files = {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in bundle.rglob('*') if p.is_file() and p.name != 'manifest.json'}
                (bundle / 'manifest.json').write_text(json.dumps({'schema': 1, 'roots': ['pkg'], 'targets': {'test': {}}, 'files': files}))

            manifest()
            repo.publish(bundle)
            first = (repo.DATA / 'current').readlink()
            self.assertEqual((repo.DATA / 'test/simple/pkg/index.html').read_text(), 'initial index')
            self.assertEqual((repo.DATA / 'runtime-cache/tiktoken/test-cache').read_bytes(), b'vocabulary')
            index.write_text('corrupt')
            with self.assertRaisesRegex(ValueError, 'Checksum'):
                repo.publish(bundle)
            self.assertEqual((repo.DATA / 'current').readlink(), first)
            index.write_text('updated index')
            wheel.unlink()
            (wheel.parent / 'pkg-2-py3-none-any.whl').write_bytes(b'updated')
            manifest()
            repo.publish(bundle)
            self.assertEqual((repo.DATA / 'test/simple/pkg/index.html').read_text(), 'updated index')
            self.assertEqual((repo.DATA / 'test/wheels/pkg-1-py3-none-any.whl').read_bytes(), b'initial')
            # Reimport is safe; a local filename collision never replaces an existing artifact.
            repo.publish(bundle)
            (wheel.parent / 'pkg-2-py3-none-any.whl').write_bytes(b'conflict')
            manifest()
            before = (repo.DATA / 'current').readlink()
            with self.assertRaisesRegex(ValueError, 'collision'):
                repo.publish(bundle)
            self.assertEqual((repo.DATA / 'current').readlink(), before)

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'escape').symlink_to('/etc/passwd')
            (root / 'manifest.json').write_text(json.dumps({'schema': 1, 'files': {'escape': 'bad'}}))
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                repo.verify(root)


if __name__ == '__main__':
    unittest.main()
