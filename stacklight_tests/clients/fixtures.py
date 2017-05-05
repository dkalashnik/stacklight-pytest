import pytest

from stacklight_tests.clients.prometheus import alertmanager_client
from stacklight_tests.clients.prometheus import prometheus_client


@pytest.fixture(scope="session")
def prometheus_api(env_config):
    prometheus_config = env_config.get("prometheus")
    api_client = prometheus_client.PrometheusClient(
        "http://{0}:{1}/".format(
            prometheus_config["prometheus_vip"],
            prometheus_config["prometheus_server_port"])
    )
    return api_client


@pytest.fixture(scope="session")
def prometheus_alerting(env_config):
    prometheus_config = env_config.get("prometheus")
    if not prometheus_config.get("use_prometheus_query_alert", True):
        alerting = alertmanager_client.AlertManagerClient(
            "http://{0}:{1}/".format(
                prometheus_config["prometheus_vip"],
                prometheus_config["prometheus_alertmanager"])
        )
    else:
        alerting = (
            alertmanager_client.PrometheusQueryAlertClient(
                "http://{0}:{1}/".format(
                    prometheus_config["prometheus_vip"],
                    prometheus_config["prometheus_server_port"])
            )
        )
    return alerting
