import pytest

from client_manager import check_rabbit_mq_disk_alarms
from client_manager import TimeoutError

FETCH_TIMEOUT = 10  # Timeout for fetch time normalization failing/passing


class TestAlerts(object):
    """Test alerting service for openstack deployments with Stacklight"""
    def test_success_alerts(self):
        check_rabbit_mq_disk_alarms({'hostname': 'node-3'}, None, None,
                                    timeout=FETCH_TIMEOUT)

    def test_fail_alerts(self):
        # TODO Custom error: TriggerTimeout
        # TimeoutError: Alarm of type: service: entity: rabbitmq-cluster,
        # source:disk, hostname: node-4, value: 0 wasn't triggered
        with pytest.raises(TimeoutError):
            check_rabbit_mq_disk_alarms({'hostname': 'node-4'}, None, None,
                                        timeout=10)
