"""Runtime configuration, entirely environment-driven.

The defaults reproduce the production bind-mounts exactly, so nothing changes
unless an environment variable is set.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CORS_ORIGINS = "https://browser.herz-campaigns.de"


def _config_root() -> Path:
    # Absolute, so that a relative IGMK_CONFIG_ROOT is resolved against the
    # working directory rather than the Flask app root (igmk_api/), which
    # send_file would otherwise use.
    return Path(os.environ.get("IGMK_CONFIG_ROOT", "/config")).resolve()


def _cors_origins() -> list[str]:
    raw = os.environ.get("IGMK_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(slots=True)
class Settings:
    #: Config tree holding plots/, instruments/ and sites/.
    config_root: Path = field(default_factory=_config_root)
    #: Origins allowed to call the API from a browser.
    cors_origins: list[str] = field(default_factory=_cors_origins)

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
