from __future__ import print_function
import pytest


class TestKibana(object):

    def test_haproxy_logs(self, es_client):
        """Check logs for haproxy backends programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a haproxy logs.

        Duration 1m
        """
        assert es_client.log_is_presented('programname:haproxy')

    def test_ovs_logs(self, es_client):
        """Check logs for openvswitch programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a
               openvswitch logs.

        Duration 1m
        """
        entities = {
            'Logger:ovs AND programname:ovs-vswitchd',
            'Logger:ovs AND programname:ovsdb-server',
        }
        assert not es_client.get_absent_programs_for_group(
            entities, time_range="now-12h")

    def test_networking_logs(self, es_client):
        """Check logs for networking programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a
               networking logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.neutron AND programname:dhcp-agent',
            'Logger:openstack.neutron AND programname:l3-agent',
            'Logger:openstack.neutron AND programname:metadata-agent',
        }
        assert not es_client.get_absent_programs_for_group(entities)

    def test_glance_logs(self, es_client):
        """Check logs for glance.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.glance AND programname:api',
            'Logger:glusterfs AND programname:glusterd',
            'Logger:openstack.glance AND programname:registry',

        }
        assert not es_client.get_absent_programs_for_group(entities)

    def test_keystone_logs(self, es_client):
        """Check logs for keystone.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        # NOTE(rpromyshlennikov): there are two types of envs:
        #  with apache and with keystone standalone
        # TODO(rpromyshlennikov): add env condition checker
        # dvr_entities = {
        #     'Logger:openstack.keystone AND programname:keystone-wsgi-admin',
        #     'Logger:openstack.keystone AND programname:keystone-wsgi-main',
        #     'Logger:openstack.keystone AND programname:keystone-admin',
        #     'Logger:openstack.keystone AND programname:keystone-public',
        # }
        entities = {
            'Logger:openstack.keystone AND programname:keystone',
        }
        assert not es_client.get_absent_programs_for_group(entities)

    def test_heat_logs(self, es_client):
        """Check logs for heat.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        # Is it ok that all heat logs are aggregated in one programname?
        entities = {'Logger:openstack.heat AND programname:heat'}
        assert not es_client.get_absent_programs_for_group(entities)

    def test_cinder_logs(self, es_client):
        """Check logs for cinder.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.cinder AND programname:cinder-api',
            'Logger:openstack.cinder AND programname:cinder-backup',
            'Logger:openstack.cinder AND programname:cinder-scheduler',
            'Logger:openstack.cinder AND programname:cinder-volume',
            'Logger:openstack.cinder AND programname:cinder-manage',
        }
        assert not es_client.get_absent_programs_for_group(entities)

    def test_nova_logs(self, es_client):
        """Check logs for nova.
        Scenario:
            1. Run elasticsearch query to validate presence of a nova logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.nova AND programname:nova-api',
            'Logger:openstack.nova AND programname:nova-compute',
            'Logger:openstack.nova AND programname:nova-scheduler',
        }

        absent_logs = es_client.get_absent_programs_for_group(entities)
        conductor = 'Logger:openstack.nova AND programname:nova-conductor'
        if not es_client.log_is_presented(conductor, time_range="now-1d"):
            absent_logs.add(conductor)
        assert not absent_logs

    def test_messaging_logs(self, es_client):
        """Check logs for messaging.
        Scenario:
            1. Run elasticsearch query to validate presence of a rabbitmq logs.

        Duration 1m
        """
        query_filter = 'Logger:rabbitmq* AND programname:rabbitmq'
        assert es_client.log_is_presented(query_filter, time_range="now-1d")

    def test_horizon_logs(self, es_client):
        """Check logs for horizon.
        Scenario:
            1. Run elasticsearch query to validate presence of a horizon logs.

        Duration 1m
        """
        assert es_client.log_is_presented('programname:horizon*')

    def test_system_logs(self, es_client):
        """Check logs for linux system.
        Scenario:
            1. Run elasticsearch query to validate presence of a system logs.

        Duration 1m
        """

        entities = {
            'Logger:system.auth',
            'Logger:system.kern',
            'Logger:system.syslog',

        }
        absent_logs = es_client.get_absent_programs_for_group(entities)
        cron_filter = 'Logger:system* AND programname:CRON'
        if not es_client.log_is_presented(cron_filter, time_range="now-30m"):
            absent_logs.add(cron_filter)
        assert not absent_logs

    @pytest.mark.check_env("is_mk")
    def test_zookeeper_logs(self, es_client):
        """Check logs for zookeeper.
        Scenario:
            1. Run elasticsearch query to validate presence of a
            zookeeper logs.

        Duration 1m
        """
        assert es_client.log_is_presented(
            'Logger:contrail.zookeeper AND programname:zookeeper')

    @pytest.mark.check_env("is_mk")
    def test_cassandra_logs(self, es_client):
        """Check logs for cassandra.
        Scenario:
            1. Run elasticsearch query to validate presence of a
            cassandra logs.

        Duration 1m
        """
        entities = {
            'Logger:contrail.cassandra.system AND programname:cassandra',
            'Logger:contrail.cassandra.status AND programname:cassandra',
        }
        absent_logs = es_client.get_absent_programs_for_group(entities)
        assert not absent_logs

    @pytest.mark.check_env("is_mk")
    def test_contrail_logs(self, es_client):
        """Check logs for contrail.
        Scenario:
            1. Run elasticsearch query to validate presence of a
            contrail logs.

        Duration 1m
        """
        entities = {
            'Logger:contrail.alarm-gen*',
            'Logger:contrail.discovery*',
        }
        absent_logs = es_client.get_absent_programs_for_group(entities)
        assert not absent_logs
