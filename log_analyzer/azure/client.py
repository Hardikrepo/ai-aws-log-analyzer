"""Azure auth/client helpers shared by every Azure log source."""

from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient

from . import config


def get_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def monitor_client(subscription_id: str | None = None) -> MonitorManagementClient:
    return MonitorManagementClient(get_credential(), subscription_id or config.DEFAULT_SUBSCRIPTION_ID)
