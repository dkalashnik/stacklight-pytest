from stacklight_tests.tests import base_test


class TestSmoke(base_test.BaseLMATest):
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

        Duration 5m
        """
        self.grafana_api.check_grafana_online()
        dashboard_names = {
            "Apache", "Cinder", "Elasticsearch", "Glance", "HAProxy", "Heat",
            "Hypervisor", "InfluxDB", "Keystone", "LMA self-monitoring",
            "Memcached", "MySQL", "Neutron", "Nova", "RabbitMQ", "System"
        }
        if self.env_type == "mk":
            dashboard_names = {
                "Cassandra", "GlusterFS", "Nginx", "OpenContrail",
                "Cinder", "Elasticsearch", "Glance", "HAProxy", "Heat",
                "Hypervisor", "InfluxDB", "Keystone",
                "Memcached", "MySQL", "Neutron", "Nova", "RabbitMQ", "System"
            }
        dashboard_names = {panel_name.lower().replace(" ", "-")
                           for panel_name in dashboard_names}

        available_dashboards_names = set()
        for name in dashboard_names:
            if self.grafana_api.is_dashboard_exists(name):
                available_dashboards_names.add(name)
        msg = ("There is not enough panels in available panels, "
               "panels that are not presented: {}")
        assert dashboard_names == available_dashboards_names, (
            msg.format(dashboard_names - available_dashboards_names))

    def test_openstack_service_metrics_presented(self):
        """Verify the new metrics '<openstack._service>.api were
        created in InfluxDB

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

        Duration 5m
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
        created in InfluxDB

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

        Duration 5m
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
        nodes_statuses = self.nagios_api.get_all_nodes_statuses()
        if self.is_mk:
            hostnames = {host.fqdn for host in self.cluster.hosts}
        else:
            hostnames = {host.hostname for host in self.cluster.hosts}
        absent_hostnames = hostnames - set(nodes_statuses.keys())
        assert not absent_hostnames
        assert not any([value == "DOWN" for value in nodes_statuses.values()])
