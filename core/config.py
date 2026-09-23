from dataclasses import dataclass
from pathlib import Path


@dataclass
class CauvisConfig:
    name: str = "Cauvis"
    version: str = "0.3.0"
    debug: bool = True

    root_dir: Path = Path(__file__).resolve().parent.parent