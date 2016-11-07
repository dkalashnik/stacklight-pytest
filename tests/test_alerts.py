import pytest

from tests import base_test
from clients import influxdb_api
import custom_exceptions as exceptions
import utils


class TestAlerts(base_test.BaseLMATest):
    OKAY_STATUS = 0
    WARNING_STATUS = 1
    UNKNOWN_STATUS = 2
    CRITICAL_STATUS = 3
    DOWN_STATUS = 4

    RABBITMQ_DISK_WARNING_PERCENT = 99.99
    RABBITMQ_DISK_CRITICAL_PERCENT = 100
    RABBITMQ_MEMORY_WARNING_VALUE = 1.01
    RABBITMQ_MEMORY_CRITICAL_VALUE = 1.0001

    @classmethod
    def setup_class(cls):
        super(TestAlerts, cls).setup_class()

        cls.influxdb_api = influxdb_api.InfluxdbApi(
            address=cls.config["lma"]["influxdb_vip"],
            port=cls.config["lma"]["influxdb_port"],
            username=cls.config["lma"]["influxdb_username"],
            password=cls.config["lma"]["influxdb_password"],
            db_name=cls.config["lma"]["influxdb_db_name"]
        )

    def check_rabbit_mq_disk_alarms(self, controller, status, percent,
                                    timeout=60):

        utils.wait(lambda: self.influxdb_api.check_alarms(
            alarm_type="service",
            filter_value="rabbitmq-cluster",
            source="disk",
            hostname=controller.hostname,
            value=self.OKAY_STATUS))

        default_value = controller.execute(
            "rabbitmqctl environment | grep disk_free_limit | "
            "sed -r 's/}.+//' | sed 's|.*,||'").rstrip()

        cmd = ("rabbitmqctl -n rabbit@messaging-node-3 set_disk_free_limit $"
               "(df | grep /dev/dm- | "
               "awk '{{ printf(\"%.0f\\n\", 1024 * ((($3 + $4) * "
               "{percent} / 100) - $3))}}')")

        controller.execute(cmd.format(percent=percent))

        utils.wait(lambda: self.influxdb_api.check_alarms(
            alarm_type="service",
            filter_value="rabbitmq-cluster",
            source="disk",
            hostname=controller.hostname,
            value=status))

        controller.execute(
            "rabbitmqctl set_disk_free_limit {}".format(default_value))

        utils.wait(lambda: self.influxdb_api.check_alarms(
            alarm_type="service",
            filter_value="rabbitmq-cluster",
            source="disk",
            hostname=controller.hostname,
            value=self.OKAY_STATUS))

    def test_success_alerts(self):
        controller = self.cluster.get_by_hostname("node-3")
        self.check_rabbit_mq_disk_alarms(
            controller=controller,
            status=self.WARNING_STATUS,
            percent=self.RABBITMQ_DISK_WARNING_PERCENT)

    def test_fail_alerts(self):
        controller = self.cluster.get_by_hostname("node-4")
        with pytest.raises(exceptions.TimeoutError):
            self.check_rabbit_mq_disk_alarms(
                controller=controller,
                status=self.WARNING_STATUS,
                percent=self.RABBITMQ_DISK_WARNING_PERCENT)
