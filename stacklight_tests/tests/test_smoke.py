import pytest

from stacklight_tests.tests import base_test


class TestSmoke(base_test.BaseLMATest):

    def test_influxdb_installed(self):
        """Smoke test that checks basic features of InfluxDb.

        Scenario:
            1. Check InfluxDB package is installed
            2. Check InfluxDB is up and running
            3. Check that InfluxDB is online and can serve requests

        Duration 1m
        """
        service = "influxdb"
        self.check_service_installed(service)
        self.check_service_running(service)
        measurements, env_name = self.influxdb_api.check_influxdb_online()
        assert measurements and env_name

    def test_grafana_installed(self):
        """Smoke test that checks basic features of Grafana.

        Scenario:
            1. Check Grafana package is installed
            2. Check Grafana is up and running
            3. Check that user can login into and HTTP API is working
            4. Check that access prohibited for non-authorized user

        Duration 1m
        """
        self.check_service_installed("grafana")
        self.check_service_running("grafana-server")
        self.grafana_api.check_grafana_online()

    def test_nagios_installed(self, destructive):
        """Smoke test that checks basic features of Nagios.

        Scenario:
            1. Check that hosts page is available
            2. Check that services page is available
            3. Check that access prohibited for non-authorized user

        Duration 1m
        """
        hosts = self.nagios_api.get_all_nodes_statuses()
        services = self.nagios_api.get_all_services_statuses()
        assert hosts and services
        # Negative testing
        origin_password = self.nagios_api.password

        def set_origin_password():
            self.nagios_api.password = origin_password
            self.nagios_api.nagios_url = self.nagios_api.format_url()
        destructive.append(set_origin_password)
        self.nagios_api.password = "rogue"
        self.nagios_api.nagios_url = self.nagios_api.format_url()
        for page in self.nagios_api.pages.keys():
            self.nagios_api.get_page(page, expected_codes=(401,))
        set_origin_password()

    def test_elasticsearch_installed(self):
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
        self.check_service_installed(service)
        self.check_service_running(service)
        log_result = self.elasticsearch_api.query_elasticsearch(size=10)
        log_failed_shards = log_result["_shards"]["failed"]
        log_hits = log_result["hits"]
        notify_result = self.elasticsearch_api.query_elasticsearch(size=10)
        notification_failed_shards = notify_result["_shards"]["failed"]
        notification_hits = notify_result["hits"]
        assert ((not log_failed_shards) and log_hits and
                (not notification_failed_shards) and notification_hits)

    def test_kibana_installed(self):
        """Smoke test that checks basic features of Kibana.

        Scenario:
            1. Check Kibana package is installed
            2. Check Kibana service is up and running
            3. Check Kibana frontend

        Duration 5m
        """
        self.check_service_installed("kibana")
        self.check_service_running("kibana")
        self.kibana_api.check_logs_dashboard()
        self.kibana_api.check_internal_kibana_api()

    def test_display_grafana_dashboards_toolchain(self):
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
        self.grafana_api.check_grafana_online()
        dashboard_names = (
            base_test.influxdb_grafana_api.get_all_grafana_dashboards_names())
        absent_dashboards = set()
        for name in dashboard_names:
            if not self.grafana_api.is_dashboard_exists(name):
                absent_dashboards.add(name)
        msg = ("There is not enough panels in available panels, "
               "panels that are not presented: {}")
        assert not absent_dashboards, msg.format(absent_dashboards)

    def test_openstack_service_metrics_presented(self):
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
            "swift-api",
        }
        if self.is_mk:
            services.remove("swift-api")
        query = ("select last(value) "
                 "from openstack_check_local_api "
                 "where time >= now() - 1m and service = '{service}'")
        absent_services = set()
        for service in services:
            result = self.influxdb_api.do_influxdb_query(
                query.format(service=service)).json()['results'][0]
            if "series" not in result:
                absent_services.add(service)
        assert not absent_services

    def test_openstack_services_alarms_presented(self):
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
            "swift-api-endpoint",
        }
        if not self.is_mk:
            query = ("select last(value) "
                     "from service_status "
                     "where time >= now() - 1m "
                     "and service = '{service}' "
                     "and source='endpoint'")
        else:
            query = ("select last(value) "
                     "from status "
                     "where time >= now() - 1m "
                     "and service = '{service}' ")
            services.remove("swift-api-endpoint")
        absent_services = set()
        for service in services:
            result = self.influxdb_api.do_influxdb_query(
                query.format(service=service)).json()['results'][0]
            if "series" not in result:
                absent_services.add(service)
        assert not absent_services

    def test_nagios_hosts_are_available_by_ssh(self):
        """Check that all nodes are tracked by Nagios via ssh.

        Scenario:
            1. Open hosts page and get tracked hosts
            2. Ensure that all nodes are in "UP" status

        Duration 1m
        """
        nodes_statuses = self.nagios_api.get_all_nodes_statuses()
        if self.is_mk:
            hostnames = {host.fqdn for host in self.cluster.hosts}
        else:
            hostnames = {host.hostname for host in self.cluster.hosts}
        absent_hostnames = hostnames - set(nodes_statuses.keys())
        assert not absent_hostnames
        assert not any([value == "DOWN" for value in nodes_statuses.values()])

    @pytest.mark.parametrize("tag_value", ["region", "aggregate"])
    def test_metrics_tag(self, tag_value):
        """Check that tags presented for all metrics."""
        tag_tables = set(self.influxdb_api.get_tag_table_bindings(tag_value))
        all_tables = set(self.influxdb_api.get_all_measurements())
        absent_metrics_tables = all_tables - tag_tables
        assert not absent_metrics_tables, "Absent tables with metrics found."
