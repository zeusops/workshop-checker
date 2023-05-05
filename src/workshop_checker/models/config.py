"""Pydantic Settings version of secrets/config"""

from pydantic import BaseSettings


class Secret(BaseSettings):
    """Bot secrets"""

    sender_mail: str | None
    password: str | None
    mail_recipient: list[str] | None
    webhook_url: str | None

    class Config:
        """The config for the secret object"""

        env_prefix = "WORKSHOP_"
