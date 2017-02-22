from __future__ import print_function
import pytest

from stacklight_tests.tests import base_test
from stacklight_tests import utils


env_type = utils.load_config().get("env", {}).get("type", "")
default_time_range = "now-1m"
if env_type != "mk":
    default_time_range = "now-15m"


class TestKibana(base_test.BaseLMATest):
    def log_is_presented(self, query_filter, time_range=default_time_range):
        # type: (str) -> None
        res = self.es_kibana_api.query_elasticsearch(
            query_filter=query_filter, time_range=time_range)
        return len(res['hits']['hits']) > 0

    def get_absent_programs_for_group(self, program_group, **kwargs):
        return {program for program in program_group
                if not self.log_is_presented(program, **kwargs)}

    def test_haproxy_logs(self):
        """Check logs for haproxy backends programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a haproxy logs.

        Duration 1m
        """
        assert self.log_is_presented('programname:haproxy')

    def test_ovs_logs(self):
        """Check logs for openvswitch programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a
               openvswitch logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.neutron AND '
            'programname:neutron-openvswitch-agent',
            'Logger:openstack.neutron AND programname:openvswitch-agent',

        }
        if self.is_mk:
            entities = {
                'Logger:ovs AND programname:ovs-vswitchd',
                'Logger:ovs AND programname:ovsdb-server',
            }
        assert not self.get_absent_programs_for_group(entities,
                                                      time_range="now-12h")

    def test_networking_logs(self):
        """Check logs for networking programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a
               networking logs.

        Duration 1m
        """
        agent_entities = {
            'Logger:openstack.neutron AND programname:dhcp-agent',
            'Logger:openstack.neutron AND programname:l3-agent',
            'Logger:openstack.neutron AND programname:metadata-agent',
        }
        entities = {
            'Logger:openstack.neutron AND programname:server',
        }
        if not self.is_mk:
            entities = agent_entities.union(entities)
        assert not self.get_absent_programs_for_group(entities)

    @pytest.mark.check_env("is_fuel")
    def test_swift_logs(self):
        """Check logs for swift.
        Scenario:
            1. Run elasticsearch query to validate presence of a swift logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.swift AND programname:swift-account-server',
            'Logger:openstack.swift AND programname:swift-container-server',
            'Logger:openstack.swift AND programname:swift-object-server',
            'Logger:openstack.swift AND programname:swift-proxy-server'
        }
        assert not self.get_absent_programs_for_group(entities)

    def test_glance_logs(self):
        """Check logs for glance.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.glance AND programname:api',
            'Logger:openstack.glance AND programname:glare',
            'Logger:openstack.glance AND programname:registry',
        }
        if self.is_mk:
            entities = {
                'Logger:openstack.glance AND programname:api',
                'Logger:glusterfs AND programname:glusterd',
                'Logger:openstack.glance AND programname:registry',

            }

        assert not self.get_absent_programs_for_group(entities)

    def test_keystone_logs(self):
        """Check logs for keystone.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.keystone AND programname:keystone-wsgi-admin',
            'Logger:openstack.keystone AND programname:keystone-wsgi-main',
            'Logger:openstack.keystone AND programname:keystone-admin',
            'Logger:openstack.keystone AND programname:keystone-public',
        }
        if self.is_mk:
            # Is it a bug that all keystone logs are aggregated
            # in one programname?
            entities = {
                'Logger:openstack.keystone AND programname:keystone',
            }

        assert not self.get_absent_programs_for_group(entities)

    def test_heat_logs(self):
        """Check logs for heat.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 1m
        """
        entities = {
            'Logger:openstack.heat AND programname:heat-api',
            'Logger:openstack.heat AND programname:heat-api-cfn',
            'Logger:openstack.heat AND programname:heat-api-cloudwatch',
            'Logger:openstack.heat AND programname:heat-engine',
        }
        if self.is_mk:
            # Is it ok that all heat logs are aggregated in one programname?
            entities = {'Logger:openstack.heat AND programname:heat'}
        assert not self.get_absent_programs_for_group(entities)

    def test_cinder_logs(self):
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
        }
        if self.is_mk:
            entities.add(
                'Logger:openstack.cinder AND programname:cinder-manage')
        assert not self.get_absent_programs_for_group(entities)

    def test_nova_logs(self):
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

        absent_logs = self.get_absent_programs_for_group(entities)
        conductor = 'Logger:openstack.nova AND programname:nova-conductor'
        if not self.log_is_presented(conductor, time_range="now-1d"):
            absent_logs.add(conductor)
        assert not absent_logs

    def test_messaging_logs(self):
        """Check logs for messaging.
        Scenario:
            1. Run elasticsearch query to validate presence of a rabbitmq logs.

        Duration 1m
        """
        query_filter = 'Logger:pacemaker AND rabbitmq*'
        if self.is_mk:
            query_filter = 'Logger:rabbitmq* AND programname:rabbitmq'
        assert self.log_is_presented(query_filter, time_range="now-1d")

    def test_horizon_logs(self):
        """Check logs for horizon.
        Scenario:
            1. Run elasticsearch query to validate presence of a horizon logs.

        Duration 1m
        """
        assert self.log_is_presented('programname:horizon*')

    def test_system_logs(self):
        """Check logs for linux system.
        Scenario:
            1. Run elasticsearch query to validate presence of a system logs.

        Duration 1m
        """

        if self.is_mk:
            entities = {
                'Logger:system.auth',
                'Logger:system.kern',
                'Logger:system.syslog',

            }
            absent_logs = self.get_absent_programs_for_group(entities)
            cron_filter = 'Logger:system* AND programname:CRON'
            if not self.log_is_presented(cron_filter, time_range="now-30m"):
                absent_logs.add(cron_filter)
            assert not absent_logs
        else:
            entities = {
                'Logger:system.auth',
                'Logger:system.cron',
                'Logger:system.daemon',
                'Logger:system.messages',
                'Logger:system.syslog',
            }
        assert not self.get_absent_programs_for_group(entities)

    @pytest.mark.check_env("is_mk")
    def test_zookeeper_logs(self):
        """Check logs for zookeeper.
        Scenario:
            1. Run elasticsearch query to validate presence of a
            zookeeper logs.

        Duration 1m
        """
        assert self.log_is_presented(
            'Logger:contrail.zookeeper AND programname:zookeeper')

    @pytest.mark.check_env("is_mk")
    def test_cassandra_logs(self):
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
        absent_logs = self.get_absent_programs_for_group(entities)
        assert not absent_logs

    @pytest.mark.check_env("is_mk")
    def test_contrail_logs(self):
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
        absent_logs = self.get_absent_programs_for_group(entities)
        assert not absent_logs
