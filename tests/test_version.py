import pytest
import pathlib
import aiodal
import toml  # type: ignore


def test_pyproject_version_sync():
    path = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = toml.loads(open(str(path)).read())
    pyproject_version = pyproject["tool"]["poetry"]["version"]

    package_init_version = aiodal.__version__

    assert package_init_version == pyproject_version
