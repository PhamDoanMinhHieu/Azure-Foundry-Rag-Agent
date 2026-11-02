from app.config import APPLICATIONINSIGHTS_CONNECTION_STRING


def setup_telemetry() -> None:
    if not APPLICATIONINSIGHTS_CONNECTION_STRING:
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
