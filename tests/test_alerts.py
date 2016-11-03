import pytest

from client_manager import check_rabbit_mq_disk_alarms
from client_manager import TimeoutError
from client_manager import GeneralActionsClient
from client_manager import WARNING_STATUS
from client_manager import RABBITMQ_DISK_WARNING_PERCENT

FETCH_TIMEOUT = 10  # Timeout for fetch time normalization failing/passing

priv_key = open('./fixtures/id_rsa').read()
ssh_client = GeneralActionsClient('10.109.0.3',
                                  'root',
                                  private_key=priv_key)


class TestAlerts(object):
    """Test alerting service for openstack deployments with Stacklight"""
    def test_success_alerts(self):
        check_rabbit_mq_disk_alarms({'hostname': 'node-3'},
                                    WARNING_STATUS,
                                    RABBITMQ_DISK_WARNING_PERCENT,
                                    ssh_client,
                                    timeout=FETCH_TIMEOUT)

    def test_fail_alerts(self):
        # TODO Custom error: TriggerTimeout
        # TimeoutError: Alarm of type: service: entity: rabbitmq-cluster,
        # source:disk, hostname: node-4, value: 0 wasn't triggered
        with pytest.raises(TimeoutError):
            check_rabbit_mq_disk_alarms({'hostname': 'node-4'},
                                        WARNING_STATUS,
                                        RABBITMQ_DISK_WARNING_PERCENT,
                                        ssh_client,
                                        timeout=FETCH_TIMEOUT)
