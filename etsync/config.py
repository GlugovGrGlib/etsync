from pathlib import Path

from dynaconf import Dynaconf, Validator

_root = Path(__file__).resolve().parent.parent

settings = Dynaconf(
    envvar_prefix="ETSYNC",
    settings_files=[str(_root / "settings.toml"), str(_root / ".secrets.toml")],
    environments=True,
    default_env="default",
    env_switcher="ETSYNC_ENV",
    validators=[
        Validator("api_base_url", default="https://api.etsy.com"),
        Validator("data_dir", default=str(_root / ".etsync")),
    ],
)


def get_data_dir() -> Path:
    return Path(settings.data_dir).expanduser() / settings.current_env.lower()
