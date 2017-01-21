import pytest

from stacklight_tests.tests import base_test


class TestSmoke(base_test.BaseLMATest):
    def test_logs_in_elasticsearch(self):
        """Check that logs of all known services are presented
        in Elasticsearch

        Scenario:
            1. Check that logs are collected for all known services
               to current Elasticsearch index

        Duration 5m
        """
        known_services = {
            'CRON', 'api', 'attrd',
            'cib',
            'cinder-api', 'cinder-backup', 'cinder-scheduler', 'cinder-volume',
            'crmd',
            'dhcp-agent',
            'glare',
            'haproxy',
            'heat-api', 'heat-api-cfn', 'heat-api-cloudwatch', 'heat-engine',
            'horizon_access',
            'keystone-admin', 'keystone-public',
            'keystone-wsgi-admin', 'keystone-wsgi-main',
            'l3-agent',
            'liberasurecode',
            'lrmd',
            'metadata-agent',
            'nagios3',
            'neutron-openvswitch-agent',
            'nova-api', 'nova-compute', 'nova-conductor', 'nova-scheduler',
            'ocf-mysql-wss', 'ocf-ns_IPaddr2', 'ocf-ns_apache(apache2-nagios)',
            'ocf-ns_conntrackd', 'ocf-ns_dns', 'ocf-ns_haproxy', 'ocf-ns_ntp',
            'ocf-ns_vrouter',
            'openvswitch-agent',
            'pengine',
            'registry',
            'server',
            'su',
            'swift-account-server', 'swift-container-server',
            'swift-object-server', 'swift-proxy-server',
            'xinetd'
        }
        # NOTE(some services, available only after deploy)
        # after_deploy_services = {
        #     'dnsmasq', 'dnsmasq-dhcp',
        #     'kernel',
        #     'ntpd', 'ntpdate',
        #     'ovs-vswitchd',
        #     'rabbitmq',
        #     'sshd',
        #
        # }
        for service in known_services:
            output = self.es_kibana_api.query_elasticsearch(
                index_type="log",
                query_filter="programname:{service}".format(service=service))
            assert output['hits']['total'] != 0, (
                "Indexes don't contain {service} logs".format(service=service))

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
        table = "openstack_check_local_api"
        services = (
            "cinder-api",
            "cinder-v2-api",
            "glance-api",
            "heat-api",
            "heat-cfn-api",
            "keystone-public-api",
            "neutron-api",
            "nova-api",
            "swift-api",
            "swift-s3-api",
        )
        query = ("select last(value) "
                 "from {table} "
                 "where time >= now() - 1m and service = '{service}'")
        for service in services:
            query = query.format(table=table, service=service)
            assert len(self.influxdb_api.do_influxdb_query(
                query).json()['results'][0])

    @pytest.mark.check_env("is_fuel")
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
        table = "service_status"
        services = (
            "cinder-api-endpoint",
            "cinder-v2-api-endpoint",
            "glance-api-endpoint",
            "heat-api-endpoint",
            "heat-cfn-api-endpoint",
            "keystone-public-api-endpoint",
            "neutron-api-endpoint",
            "nova-api-endpoint",
            "swift-api-endpoint",
            "swift-s3-api-endpoint",
        )
        query = ("select last(value) "
                 "from {table} "
                 "where time >= now() - 1m "
                 "and service = '{service}' "
                 "and source='endpoint'")
        for service in services:
            query = query.format(table=table, service=service)
            assert len(self.influxdb_api.do_influxdb_query(
                query).json()['results'][0])

    def test_nagios_hosts_are_available_by_ssh(self):
        nodes_statuses = self.nagios_api.get_all_nodes_statuses()
        nodes = [host.hostname for host in self.cluster.hosts]
        for node in nodes:
            assert node in nodes_statuses.keys()
        assert not any([value == "DOWN" for value in nodes_statuses.values()])
