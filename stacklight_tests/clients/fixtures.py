import pytest

from stacklight_tests.clients.prometheus import alertmanager_client
from stacklight_tests.clients.prometheus import prometheus_client


@pytest.fixture(scope="session")
def prometheus_api(prometheus_config):
    api_client = prometheus_client.PrometheusClient(
        "http://{0}:{1}/".format(
            prometheus_config["prometheus_vip"],
            prometheus_config["prometheus_server_port"])
    )
    return api_client


@pytest.fixture(scope="session")
def prometheus_native_alerting(prometheus_config):
    alerting = alertmanager_client.AlertManagerClient(
        "http://{0}:{1}/".format(
            prometheus_config["prometheus_vip"],
            prometheus_config["prometheus_alertmanager"])
    )
    return alerting


@pytest.fixture(scope="session")
def prometheus_alerting(prometheus_config, prometheus_native_alerting):
    if not prometheus_config.get("use_prometheus_query_alert", True):
        alerting = prometheus_native_alerting
    else:
        alerting = (
            alertmanager_client.PrometheusQueryAlertClient(
                "http://{0}:{1}/".format(
                    prometheus_config["prometheus_vip"],
                    prometheus_config["prometheus_server_port"])
            )
        )
    return alerting
