"""Runtime configuration, entirely environment-driven.

The defaults reproduce the production bind-mounts exactly, so nothing changes
unless an environment variable is set. Local development sets
``IGMK_CONFIG_ROOT`` instead of editing source and reverting before commit.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    #: Root of the config tree; holds plots/, instruments/ and sites/.
    #: Production bind-mounts /data/obs/api_config/default here.
    config_root: Path = Path(os.environ.get("IGMK_CONFIG_ROOT", "/config"))

    def __post_init__(self) -> None:
        # The root is made absolute up front. A relative IGMK_CONFIG_ROOT would
        # otherwise be resolved by ``send_file`` against the Flask app root
        # (igmk_api/) rather than the working directory, so
        # ``IGMK_CONFIG_ROOT=./config`` would 500 on /sites/{id} and
        # /instruments/{id} while every other route worked.
        object.__setattr__(self, "config_root", self.config_root.resolve())

    @property
    def plots_dir(self) -> Path:
        return self.config_root / "plots"

    @property
    def instruments_dir(self) -> Path:
        return self.config_root / "instruments"

    @property
    def sites_dir(self) -> Path:
        return self.config_root / "sites"


settings = Settings()
