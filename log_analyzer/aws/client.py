"""Boto3 session/client helpers shared by every log source."""

import boto3

from . import config


def get_session(profile: str | None = None, region: str | None = None) -> boto3.Session:
    return boto3.Session(
        profile_name=profile,
        region_name=region or config.DEFAULT_REGION,
    )


def client(service: str, profile: str | None = None, region: str | None = None):
    return get_session(profile, region).client(service)
