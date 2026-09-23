import json
import os
import subprocess
from typing import Any, Callable


Collector = Callable[[], dict[str, Any]]


class SystemDiagnosticsRuntime:
    """Read-only Windows performance snapshot and deterministic analysis."""

    def __init__(
        self,
        collector: Collector | None = None,
    ):
        self._collector = collector or self._collect_windows

    def performance_snapshot(self) -> dict[str, Any]:
        data = dict(self._collector())
        findings = self._findings(data)

        return {
            "snapshot": data,
            "findings": findings,
            "verified_runtime_observation": True,
            "read_only": True,
        }

    @staticmethod
    def _findings(data: dict[str, Any]) -> list[str]:
        findings = []

        cpu = float(data.get("cpu_percent") or 0)
        memory = float(data.get("memory_percent") or 0)

        if cpu >= 85:
            findings.append(
                f"CPU usage is very high at about {cpu:.0f}%."
            )
        elif cpu >= 65:
            findings.append(
                f"CPU usage is elevated at about {cpu:.0f}%."
            )

        if memory >= 90:
            findings.append(
                f"Memory usage is very high at about {memory:.0f}%."
            )
        elif memory >= 75:
            findings.append(
                f"Memory usage is elevated at about {memory:.0f}%."
            )

        low_disks = []

        for disk in data.get("disks", []) or []:
            try:
                free = float(disk.get("free_percent") or 100)
            except Exception:
                continue

            if free < 10:
                low_disks.append(
                    str(disk.get("drive") or "disk")
                )

        if low_disks:
            findings.append(
                "Very low free space detected on: "
                + ", ".join(low_disks)
                + "."
            )

        if not findings:
            findings.append(
                "No obvious CPU, memory, or critically-low disk-space "
                "bottleneck was detected in this snapshot."
            )

        top_memory = data.get("top_memory_processes") or []

        if top_memory:
            first = top_memory[0]
            findings.append(
                "Top memory process in the snapshot: "
                + str(first.get("name") or "unknown")
                + " (PID "
                + str(first.get("pid") or "?")
                + ")."
            )

        return findings

    @staticmethod
    def _collect_windows() -> dict[str, Any]:
        if os.name != "nt":
            raise RuntimeError(
                "System diagnostics currently support Windows only."
            )

        script = r"""
$ErrorActionPreference = "Stop"
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
$totalMem = [double]$os.TotalVisibleMemorySize * 1KB
$freeMem = [double]$os.FreePhysicalMemory * 1KB
$memPct = if ($totalMem -gt 0) { (($totalMem-$freeMem)/$totalMem)*100 } else { 0 }

$disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    $freePct = if ($_.Size -gt 0) { ($_.FreeSpace/$_.Size)*100 } else { 0 }
    [PSCustomObject]@{
        drive = $_.DeviceID
        size_gb = [math]::Round($_.Size/1GB,2)
        free_gb = [math]::Round($_.FreeSpace/1GB,2)
        free_percent = [math]::Round($freePct,1)
    }
}

$proc = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 | ForEach-Object {
    [PSCustomObject]@{
        name = $_.ProcessName
        pid = $_.Id
        memory_mb = [math]::Round($_.WorkingSet64/1MB,1)
        cpu_seconds = if ($null -ne $_.CPU) { [math]::Round($_.CPU,1) } else { 0 }
    }
}

[PSCustomObject]@{
    computer_name = $env:COMPUTERNAME
    windows = $os.Caption
    version = $os.Version
    cpu_percent = [math]::Round($cpu.Average,1)
    memory_total_gb = [math]::Round($totalMem/1GB,2)
    memory_free_gb = [math]::Round($freeMem/1GB,2)
    memory_percent = [math]::Round($memPct,1)
    last_boot = $os.LastBootUpTime
    disks = @($disks)
    top_memory_processes = @($proc)
} | ConvertTo-Json -Depth 6 -Compress
"""

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Windows diagnostic collection failed: "
                + (result.stderr or result.stdout).strip()
            )

        payload = json.loads(
            result.stdout.strip()
        )

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Windows diagnostics returned an unexpected payload."
            )

        return payload
