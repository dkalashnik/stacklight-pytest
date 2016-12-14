from __future__ import print_function
import pytest

from stacklight_tests.tests import base_test


class TestKibana(base_test.BaseLMATest):
    def check_program(self, program_name):
        # type: (str) -> None
        res = self.es_kibana_api.query_elasticsearch(
            index_type='log',
            query_filter='{program_name}'.format(
                program_name=program_name))

        assert len(res['hits']['hits']) > 0

    @pytest.mark.mk
    def test_networking_logs(self):
        """Check logs for networking programs.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'haproxy',
            'ovsdb-server',
#            'ovs-vswitchd',
            'dhcp-agent',
            'metadata-agent',
            'neutron-netns-cleanup',
            'openvswitch-agent',
            'neutron-openvswitch-agent',
            'server',
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_swift_logs(self):
        """Check logs for swift.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'swift-container-server',  # TODO(akostrikov) swift?
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_glance_logs(self):
        """Check logs for glance.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'glusterd',  # TODO(akostrikov) any other services?
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_keystone_logs(self):
        """Check logs for keystone.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'keystone-wsgi-admin',
            'keystone-wsgi-main',
            'keystone-wsgi-main',
            'keystone-admin',
            'keystone-manage',  # TODO(akostrikov) How it should be triggered
            'keystone-public',
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_heat_logs(self):
        """Check logs for heat.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'heat-api-cfn',
            'heat-api-cloudwatch',
            'heat-engine',
            'heat-api',
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_cinder_logs(self):
        """Check logs for cinder.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'cinder-api',
            'cinder-manage',  # TODO(akostrikov) How it should be triggered
            'cinder-scheduler',
            'cinder-backup',
            'cinder-volume',
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_nova_logs(self):
        """Check logs for nova.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'nova-scheduler',
            'libvirt',  # TODO(akostrikov) need to fix in mk
            'nova-api',
            'nova-compute',
            'nova-conductor',
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_messaging_logs(self):
        """Check logs for messaging.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'rabbitmq*',  # TODO(akostrikov) need to fix in mk
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_horizon_logs(self):
        """Check logs for horizon.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'horizon*',  # TODO(akostrikov) need to fix in mk
        }:
            self.check_program(program_name)

    @pytest.mark.mk
    def test_system_logs(self):
        """Check logs for linux system.
        Scenario:
            1. Run elasticsearch query to validate presence of a service logs.

        Duration 10m
        """
        for program_name in {
            'cron',
#            'kern',  TODO(akostrikov) need to find more concrete logs
#            'syslog',
#            'messages',
            'debug',
        }:
            self.check_program(program_name)
