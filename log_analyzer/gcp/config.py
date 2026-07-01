"""GCP-specific configuration."""

import os

DEFAULT_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
