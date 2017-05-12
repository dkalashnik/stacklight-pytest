import pytest

from stacklight_tests.clients import influxdb_grafana_api


def check_service_installed(cluster, name, role=None):
    """Checks that service is installed on nodes with provided role."""
    if role is None:
        role = "monitoring"
    nodes = cluster.filter_by_role(role)
    for node in nodes:
        node.os.check_package_installed(name)


def check_service_running(cluster, name, role=None):
    """Checks that service is running on nodes with provided role."""
    if role is None:
        role = "monitoring"
    nodes = cluster.filter_by_role(role)
    for node in nodes:
        node.os.manage_service(name, "status")


class TestSmoke(object):

    def test_influxdb_installed(self, cluster, influxdb_client):
        """Smoke test that checks basic features of InfluxDb.

        Scenario:
            1. Check InfluxDB package is installed
            2. Check InfluxDB is up and running
            3. Check that InfluxDB is online and can serve requests

        Duration 1m
        """
        service = "influxdb"
        check_service_installed(cluster, service)
        check_service_running(cluster, service)
        measurements, env_name = influxdb_client.check_influxdb_online()
        assert measurements and env_name

    def test_grafana_installed(self, cluster, grafana_client):
        """Smoke test that checks basic features of Grafana.

        Scenario:
            1. Check Grafana package is installed
            2. Check Grafana is up and running
            3. Check that user can login into and HTTP API is working
            4. Check that access prohibited for non-authorized user

        Duration 1m
        """
        check_service_installed(cluster, "grafana")
        check_service_running(cluster, "grafana-server")
        grafana_client.check_grafana_online()

    def test_nagios_installed(self, destructive, nagios_client):
        """Smoke test that checks basic features of Nagios.

        Scenario:
            1. Check that hosts page is available
            2. Check that services page is available
            3. Check that access prohibited for non-authorized user

        Duration 1m
        """
        hosts = nagios_client.get_all_nodes_statuses()
        services = nagios_client.get_all_services_statuses()
        assert hosts and services
        # Negative testing
        origin_password = nagios_client.password

        def set_origin_password():
            nagios_client.password = origin_password
            nagios_client.nagios_url = nagios_client.format_url()
        destructive.append(set_origin_password)
        nagios_client.password = "rogue"
        nagios_client.nagios_url = nagios_client.format_url()
        for page in nagios_client.pages.keys():
            nagios_client.get_page(page, expected_codes=(401,))
        set_origin_password()

    def test_elasticsearch_installed(self, cluster, es_client):
        """Smoke test that checks basic features of Elasticsearch.

        Scenario:
            1. Check Elasticsearch package is installed
            2. Check Elasticsearch is up and running
            3. Check that elasticsearch is online
            4. Check logs queries
            5. Check notification queries

        Duration 1m
        """
        service = "elasticsearch"
        check_service_installed(cluster, service)
        check_service_running(cluster, service)
        log_result = es_client.query_elasticsearch(size=10)
        log_failed_shards = log_result["_shards"]["failed"]
        log_hits = log_result["hits"]
        notify_result = es_client.query_elasticsearch(size=10)
        notification_failed_shards = notify_result["_shards"]["failed"]
        notification_hits = notify_result["hits"]
        assert ((not log_failed_shards) and log_hits and
                (not notification_failed_shards) and notification_hits)

    def test_kibana_installed(self, cluster, kibana_client):
        """Smoke test that checks basic features of Kibana.

        Scenario:
            1. Check Kibana package is installed
            2. Check Kibana service is up and running
            3. Check Kibana frontend

        Duration 5m
        """
        service = "kibana"
        check_service_installed(cluster, service)
        check_service_running(cluster, service)
        kibana_client.check_logs_dashboard()
        kibana_client.check_internal_kibana_api()

    def test_display_grafana_dashboards_toolchain(self, grafana_client):
        """Verify that the dashboards show up in the Grafana UI.

        Scenario:
            1. Go to the Main dashboard and verify that everything is ok
            2. Repeat the previous step for the following dashboards:
                * Apache
                * Cinder
                * Elasticsearch
                * Glance
                * HAProxy
                * Heat
                * Hypervisor
                * InfluxDB
                * Keystone
                * LMA self-monitoring
                * Memcached
                * MySQL
                * Neutron
                * Nova
                * RabbitMQ
                * System

        Duration 1m
        """
        grafana_client.check_grafana_online()
        dashboard_names = (
            influxdb_grafana_api.get_all_grafana_dashboards_names())
        absent_dashboards = set()
        for name in dashboard_names:
            if not grafana_client.is_dashboard_exists(name):
                absent_dashboards.add(name)
        msg = ("There is not enough panels in available panels, "
               "panels that are not presented: {}")
        assert not absent_dashboards, msg.format(absent_dashboards)

    def test_openstack_service_metrics_presented(self, influxdb_client):
        """Verify the new metrics '<openstack._service>.api were
        created in InfluxDB.

        Scenario:
            1. Check "cinder-api" metric in InfluxDB
            2. Repeat the previous step for the following services:
                * "cinder-v2-api"
                * "glance-api"
                * "heat-api"
                * "heat-cfn-api"
                * "keystone-public-api"
                * "neutron-api"
                * "nova-api"
                * "swift-api"
                * "swift-s3-api"

        Duration 1m
        """
        services = {
            "cinder-api",
            "glance-api",
            "heat-api",
            "heat-cfn-api",
            "keystone-public-api",
            "neutron-api",
            "nova-api",
        }
        query = ("select last(value) "
                 "from openstack_check_local_api "
                 "where time >= now() - 1m and service = '{service}'")
        absent_services = set()
        for service in services:
            result = influxdb_client.do_influxdb_query(
                query.format(service=service)).json()['results'][0]
            if "series" not in result:
                absent_services.add(service)
        assert not absent_services

    def test_openstack_services_alarms_presented(self, influxdb_client):
        """Verify that alarms for ''openstack_<service>_api'' were
        created in InfluxDB.

        Scenario:
            1. Check "cinder-api-endpoint" alarm in InfluxDB
            2. Repeat the previous step for the following endpoints:
                * "cinder-v2-api-endpoint"
                * "glance-api-endpoint"
                * "heat-api-endpoint"
                * "heat-cfn-api-endpoint"
                * "keystone-public-api-endpoint"
                * "neutron-api-endpoint"
                * "nova-api-endpoint"
                * "swift-api-endpoint"
                * "swift-s3-api-endpoint"

        Duration 1m
        """
        services = {
            "cinder-api-endpoint",
            "glance-api-endpoint",
            "heat-api-endpoint",
            "heat-cfn-api-endpoint",
            "keystone-public-api-endpoint",
            "neutron-api-endpoint",
            "nova-api-endpoint",
        }

        query = ("select last(value) "
                 "from status "
                 "where time >= now() - 1m "
                 "and service = '{service}' ")
        absent_services = set()
        for service in services:
            result = influxdb_client.do_influxdb_query(
                query.format(service=service)).json()['results'][0]
            if "series" not in result:
                absent_services.add(service)
        assert not absent_services

    def test_nagios_hosts_are_available_by_ssh(self, cluster, nagios_client):
        """Check that all nodes are tracked by Nagios via ssh.

        Scenario:
            1. Open hosts page and get tracked hosts
            2. Ensure that all nodes are in "UP" status

        Duration 1m
        """
        nodes_statuses = nagios_client.get_all_nodes_statuses()
        hostnames = {host.fqdn for host in cluster.hosts}
        absent_hostnames = hostnames - set(nodes_statuses.keys())
        assert not absent_hostnames
        assert not any([value == "DOWN" for value in nodes_statuses.values()])

    @pytest.mark.parametrize("tag_value", ["region", "aggregate"])
    def test_metrics_tag(self, influxdb_client, tag_value):
        """Check that tags presented for all metrics."""
        tag_tables = set(influxdb_client.get_tag_table_bindings(tag_value))
        all_tables = set(influxdb_client.get_all_measurements())
        absent_metrics_tables = all_tables - tag_tables
        assert not absent_metrics_tables, "Absent tables with metrics found."
