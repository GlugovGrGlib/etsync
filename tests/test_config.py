import os
from pathlib import Path

from dynaconf import Dynaconf, Validator


def _make_settings(tmp_path: Path, settings_content: str, secrets_content: str = "") -> Dynaconf:
    """Create a fresh Dynaconf instance from temp files."""
    settings_file = tmp_path / "settings.toml"
    secrets_file = tmp_path / ".secrets.toml"
    settings_file.write_text(settings_content)
    secrets_file.write_text(secrets_content)

    return Dynaconf(
        envvar_prefix="ETSYNC",
        settings_files=[str(settings_file), str(secrets_file)],
        environments=True,
        env_switcher="ETSYNC_ENV",
        validators=[
            Validator("api_base_url", default="https://api.etsy.com"),
            Validator("data_dir", default="~/.etsync/data"),
        ],
    )


def test_valid_config_loads(tmp_path: Path):
    s = _make_settings(
        tmp_path,
        '[default]\nshop_id = 123\ndata_dir = "/tmp/test"',
        '[default]\napi_keystring = "test_key"',
    )
    s.validators.validate()
    assert s.shop_id == 123
    assert s.data_dir == "/tmp/test"
    assert s.api_keystring == "test_key"


def test_defaults_applied(tmp_path: Path):
    s = _make_settings(tmp_path, "[default]\nshop_id = 456")
    s.validators.validate()
    assert s.api_base_url == "https://api.etsy.com"
    assert s.data_dir == "~/.etsync/data"


def test_shop_id_from_secrets(tmp_path: Path):
    s = _make_settings(
        tmp_path,
        "[default]\n",
        '[default]\napi_keystring = "key"\nshop_id = 999',
    )
    s.validators.validate()
    assert s.shop_id == 999
    assert s.api_keystring == "key"


def test_environment_switching(tmp_path: Path):
    content = '[default]\nshop_id = 1\n\n[shop2]\nshop_id = 2\ndata_dir = "/tmp/shop2"'
    old = os.environ.get("ETSYNC_ENV")
    os.environ["ETSYNC_ENV"] = "shop2"
    try:
        s = _make_settings(tmp_path, content)
        s.validators.validate()
        assert s.shop_id == 2
        assert s.data_dir == "/tmp/shop2"
    finally:
        if old is None:
            os.environ.pop("ETSYNC_ENV", None)
        else:
            os.environ["ETSYNC_ENV"] = old
