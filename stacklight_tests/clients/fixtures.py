import pytest

from stacklight_tests.clients import es_kibana_api
from stacklight_tests.clients import influxdb_grafana_api
from stacklight_tests.clients.openstack import client_manager
from stacklight_tests.clients import nagios_api
from stacklight_tests.clients.prometheus import alertmanager_client
from stacklight_tests.clients.prometheus import prometheus_client


@pytest.fixture(scope="session")
def prometheus_api(prometheus_config):
    api_client = prometheus_client.get_prometheus_client_from_config(
        prometheus_config)
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


@pytest.fixture(scope="session")
def nagios_client(nagios_config):
    nagios_api_client = nagios_api.NagiosApi(
        address=nagios_config["nagios_vip"],
        port=nagios_config["nagios_port"],
        username=nagios_config["nagios_username"],
        password=nagios_config["nagios_password"],
        tls_enabled=nagios_config["nagios_tls"],
    )
    return nagios_api_client


@pytest.fixture(scope="session")
def influxdb_client(influxdb_config):
    influxdb_api = influxdb_grafana_api.get_influxdb_client_from_config(
        influxdb_config)
    return influxdb_api


@pytest.fixture(scope="session")
def grafana_datasources(env_config):
    datasources = {"influxdb": None, "prometheus": None}
    get_clients_fn = {
        "influxdb": influxdb_grafana_api.get_influxdb_client_from_config,
        "prometheus": prometheus_client.get_prometheus_client_from_config}
    for datasource in datasources.keys():
        if datasource in env_config:
            datasources[datasource] = get_clients_fn[datasource](
                env_config[datasource])
    return datasources


@pytest.fixture(scope="session")
def grafana_client(grafana_config, grafana_datasources):
    grafana_api = influxdb_grafana_api.GrafanaApi(
        address=grafana_config["grafana_vip"],
        port=grafana_config["grafana_port"],
        username=grafana_config["grafana_username"],
        password=grafana_config["grafana_password"],
        datasources=grafana_datasources,
    )
    return grafana_api


@pytest.fixture(scope="session")
def es_client(elasticsearch_config):
    elasticsearch_api = es_kibana_api.ElasticSearchApi(
        host=elasticsearch_config["elasticsearch_vip"],
        port=elasticsearch_config["elasticsearch_port"],
    )
    return elasticsearch_api


@pytest.fixture(scope="session")
def kibana_client(elasticsearch_config):
    kibana_api = es_kibana_api.KibanaApi(
        host=elasticsearch_config["elasticsearch_vip"],
        port=elasticsearch_config["kibana_port"],
    )
    return kibana_api


@pytest.fixture(scope="session")
def os_clients(keystone_config):
    auth_url = "http://{}:5000/".format(keystone_config["public_address"])
    openstack_clients = client_manager.OfficialClientManager(
        username=keystone_config["admin_name"],
        password=keystone_config["admin_password"],
        tenant_name=keystone_config["admin_tenant"],
        auth_url=auth_url,
        cert=False,
        domain=keystone_config.get("domain", "Default"),
    )
    return openstack_clients


@pytest.fixture(scope="session")
def os_actions(os_clients):
    return client_manager.OSCliActions(os_clients)
