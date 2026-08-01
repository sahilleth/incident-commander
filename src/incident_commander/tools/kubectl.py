"""Async kubectl subprocess helper."""

import asyncio
import json
from typing import Any

from incident_commander.config import Settings


class KubectlError(Exception):
    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


class Kubectl:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _base_cmd(self) -> list[str]:
        cmd = ["kubectl"]
        if self.settings.kubeconfig:
            cmd.extend(["--kubeconfig", self.settings.kubeconfig])
        if self.settings.kube_context:
            cmd.extend(["--context", self.settings.kube_context])
        return cmd

    async def run(self, args: list[str]) -> str:
        cmd = self._base_cmd() + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.settings.kubectl_timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise KubectlError(f"kubectl timed out: {' '.join(args)}", returncode=124)

        if proc.returncode != 0:
            err = stderr.decode().strip() or stdout.decode().strip()
            raise KubectlError(err or f"kubectl failed: {' '.join(args)}", proc.returncode)

        return stdout.decode()

    async def get_json(self, resource: str, name: str, namespace: str) -> dict[str, Any]:
        out = await self.run(
            ["get", resource, name, "-n", namespace, "-o", "json"]
        )
        return json.loads(out)

    async def list_json(
        self,
        resource: str,
        namespace: str,
        label_selector: str | None = None,
    ) -> dict[str, Any]:
        args = ["get", resource, "-n", namespace, "-o", "json"]
        if label_selector:
            args.extend(["-l", label_selector])
        out = await self.run(args)
        return json.loads(out)
