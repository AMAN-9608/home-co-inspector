"""The local app runs without the retired Streamlit interface."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_web_server_is_a_direct_dependency_without_streamlit():
    # Arrange
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())

    # Act
    dependencies = project['project']['dependencies']

    # Assert
    assert any(dependency.startswith('uvicorn') for dependency in dependencies)
    assert not any(dependency.startswith('streamlit') for dependency in dependencies)


def test_legacy_streamlit_entrypoint_is_removed():
    # Arrange
    entrypoint = ROOT / 'app.py'

    # Act and assert
    assert not entrypoint.exists()


def test_lockfile_excludes_streamlit():
    # Arrange
    lock = tomllib.loads((ROOT / 'uv.lock').read_text())

    # Act
    packages = {package['name'] for package in lock['package']}

    # Assert
    assert 'uvicorn' in packages
    assert 'streamlit' not in packages
