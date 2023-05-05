"""Test secret/config parsing"""

import os
from pathlib import Path

import yaml
from pytest_mock import MockerFixture

from workshop_checker.models.config import Secret


def test_secret_import_yaml(datadir: Path):
    """Test reading secrets as yaml"""
    with open(datadir / "sample_secret.yaml") as secret_fd:
        secret_dict = yaml.safe_load(secret_fd)
    secret_obj = Secret.parse_obj(secret_dict)
    assert (
        secret_obj.sender_mail == "sender@example.com"
    ), "Incorrect yaml secret parsing"


def test_secret_import_envvar(mocker: MockerFixture):
    """Test reading secrets from environment"""
    ENV = {
        "WORKSHOP_SENDER_MAIL": "sender@example.com",
        "WORKSHOP_PASSWORD": "email password here",
        "WORKSHOP_MAIL_RECIPIENT": '["admin@example.com", "admin2@example.com"]',
        "WORKSHOP_WEBHOOK_URL": "webhook url for discord updates",
    }
    mocker.patch.dict(os.environ, ENV)
    secret_obj = Secret()
    assert (
        secret_obj.sender_mail == "sender@example.com"
    ), "Incorrect envvar secret parsing"
