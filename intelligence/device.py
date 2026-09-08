import os
import platform
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class DeviceProfile:
    operating_system: str
    operating_system_version: str
    architecture: str
    processor: str
    cpu_cores: int
    cpu_threads: int
    memory_gb: float
    gpu_names: list[str]
    gpu_memory_gb: list[float]
    gpu_integrated: bool
    metadata: dict[str, Any]


class DeviceProfiler:
    """Detects the hardware and operating environment available to Cauvis."""

    def profile(self) -> DeviceProfile:
        memory_bytes = self._get_memory_bytes()
        memory_gb = round(memory_bytes / (1024 ** 3), 2)

        gpu_names, gpu_memory_gb = self._get_gpu_information()

        return DeviceProfile(
            operating_system=platform.system(),
            operating_system_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor() or platform.uname().processor,
            cpu_cores=os.cpu_count() or 1,
            cpu_threads=os.cpu_count() or 1,
            memory_gb=memory_gb,
            gpu_names=gpu_names,
            gpu_memory_gb=gpu_memory_gb,
            gpu_integrated=self._is_integrated_gpu(gpu_names),
            metadata={
                "hostname": platform.node(),
            },
        )

    def _get_memory_bytes(self) -> int:
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_uint32),
                    ("memory_load", ctypes.c_uint32),
                    ("total_physical", ctypes.c_uint64),
                    ("available_physical", ctypes.c_uint64),
                    ("total_page_file", ctypes.c_uint64),
                    ("available_page_file", ctypes.c_uint64),
                    ("total_virtual", ctypes.c_uint64),
                    ("available_virtual", ctypes.c_uint64),
                    ("available_extended", ctypes.c_uint64),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)

            ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            )

            return status.total_physical

        except Exception:
            return 0

    def _get_gpu_information(self) -> tuple[list[str], list[float]]:
        if platform.system() != "Windows":
            return [], []

        try:
            import subprocess

            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_VideoController | "
                    "Select-Object Name, AdapterRAM | "
                    "ConvertTo-Json -Compress"
                ),
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return [], []

            import json

            data = json.loads(result.stdout)

            if isinstance(data, dict):
                data = [data]

            names = []
            memory = []

            for gpu in data:
                name = gpu.get("Name")

                if name:
                    names.append(name)

                adapter_ram = gpu.get("AdapterRAM") or 0
                memory.append(
                    round(adapter_ram / (1024 ** 3), 2)
                )

            return names, memory

        except Exception:
            return [], []

    def _is_integrated_gpu(self, gpu_names: list[str]) -> bool:
        if not gpu_names:
            return False

        integrated_keywords = (
            "Intel",
            "Iris",
            "UHD Graphics",
            "HD Graphics",
            "Vega",
            "Radeon Graphics",
        )

        return any(
            any(keyword.lower() in gpu.lower() for keyword in integrated_keywords)
            for gpu in gpu_names
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.profile())