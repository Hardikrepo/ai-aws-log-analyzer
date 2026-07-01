"""Google Cloud auth/client helpers shared by every GCP log source."""

import google.auth
import google.cloud.logging

from . import config


def get_credentials_and_project(project: str | None = None):
    credentials, discovered_project = google.auth.default()
    return credentials, project or config.DEFAULT_PROJECT or discovered_project


def logging_client(project: str | None = None) -> google.cloud.logging.Client:
    credentials, resolved_project = get_credentials_and_project(project)
    return google.cloud.logging.Client(project=resolved_project, credentials=credentials)
