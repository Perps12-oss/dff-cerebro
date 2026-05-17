import importlib.util
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_fast_pipeline():
    root = Path(__file__).resolve().parent

    for package_name in ("cerebro", "cerebro.services", "cerebro.core"):
        if package_name not in sys.modules:
            package = types.ModuleType(package_name)
            package.__path__ = []
            sys.modules[package_name] = package

    hash_spec = importlib.util.spec_from_file_location(
        "cerebro.services.hash_cache",
        root / "hash_cache.py",
    )
    hash_module = importlib.util.module_from_spec(hash_spec)
    sys.modules["cerebro.services.hash_cache"] = hash_module
    hash_spec.loader.exec_module(hash_module)

    pipeline_spec = importlib.util.spec_from_file_location(
        "cerebro.core.fast_pipeline",
        root / "fast_pipeline.py",
    )
    pipeline_module = importlib.util.module_from_spec(pipeline_spec)
    sys.modules["cerebro.core.fast_pipeline"] = pipeline_module
    pipeline_spec.loader.exec_module(pipeline_module)
    return pipeline_module.FastPipeline


class FastPipelineCorrectnessTests(unittest.TestCase):
    def test_large_files_with_same_sample_windows_are_not_grouped(self):
        FastPipeline = _load_fast_pipeline()

        one_mib = 1024 * 1024
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "left.bin").write_bytes(
                b"A" * one_mib
                + b"X" * one_mib
                + b"B" * one_mib
                + b"Y" * one_mib
                + b"C" * one_mib
            )
            (root / "right.bin").write_bytes(
                b"A" * one_mib
                + b"Z" * one_mib
                + b"B" * one_mib
                + b"W" * one_mib
                + b"C" * one_mib
            )

            result = FastPipeline(max_workers=2).run_fast_scan(
                root,
                min_size=1,
                include_hidden=True,
                follow_symlinks=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual([], result["groups"])

    def test_identical_files_still_group(self):
        FastPipeline = _load_fast_pipeline()

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"identical payload" * 1024
            (root / "a.bin").write_bytes(payload)
            (root / "b.bin").write_bytes(payload)

            result = FastPipeline(max_workers=2).run_fast_scan(
                root,
                min_size=1,
                include_hidden=True,
                follow_symlinks=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(1, len(result["groups"]))
        self.assertEqual(2, result["groups"][0]["count"])


if __name__ == "__main__":
    unittest.main()
