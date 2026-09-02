from functools import cached_property, lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_ids(value: str, name: str, *, required: bool) -> frozenset[int]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if required and not parts:
        raise ValueError(f"{name} must contain at least one Discord snowflake")
    try:
        return frozenset(int(part) for part in parts)
    except ValueError as error:
        raise ValueError(f"{name} must be a comma-separated list of integers") from error


class CollectorSettings(BaseSettings):
    discord_bot_token: str = Field(min_length=1)
    discord_channel_ids: str = Field(min_length=1)
    discord_author_ids: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @cached_property
    def channel_ids(self) -> frozenset[int]:
        return _parse_ids(self.discord_channel_ids, "DISCORD_CHANNEL_IDS", required=True)

    @cached_property
    def author_ids(self) -> frozenset[int]:
        return _parse_ids(self.discord_author_ids, "DISCORD_AUTHOR_IDS", required=False)


@lru_cache
def get_collector_settings() -> CollectorSettings:
    return CollectorSettings()  # type: ignore[call-arg]
