"""Unit tests for kubectl subprocess wrapper.

Note: cli.py is intentionally out of scope for tools boundary tests (entry-point only).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from incident_commander.config import Settings
from incident_commander.tools.kubectl import Kubectl, KubectlError


@pytest.fixture
def kubectl(tmp_path) -> Kubectl:
    return Kubectl(
        Settings(
            incident_db_path=tmp_path / "kubectl.db",
            kubectl_timeout_seconds=1,
            kube_context="test-context",
        )
    )


def _fake_proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


@pytest.mark.asyncio
async def test_run_success_returns_stdout(kubectl):
    proc = _fake_proc(stdout=b"deployment/foo\n")
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        out = await kubectl.run(["get", "deployments", "-n", "default"])
    assert out == "deployment/foo\n"


@pytest.mark.asyncio
async def test_run_nonzero_exit_raises_kubectl_error(kubectl):
    proc = _fake_proc(returncode=1, stderr=b"Error from server")
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        with pytest.raises(KubectlError) as exc:
            await kubectl.run(["get", "pods", "-n", "default"])
    assert exc.value.returncode == 1
    assert "Error from server" in str(exc.value)


@pytest.mark.asyncio
async def test_run_timeout_kills_and_raises(kubectl):
    proc = MagicMock()
    proc.kill = MagicMock()

    async def slow_communicate():
        await asyncio.sleep(5)
        return b"", b""

    proc.communicate = slow_communicate

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        with pytest.raises(KubectlError) as exc:
            await kubectl.run(["get", "pods"])
    proc.kill.assert_called_once()
    assert exc.value.returncode == 124
    assert "timed out" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_get_json_parses_output(kubectl):
    proc = _fake_proc(stdout=b'{"kind": "Pod"}')
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        data = await kubectl.get_json("pod", "foo", "default")
    assert data == {"kind": "Pod"}
