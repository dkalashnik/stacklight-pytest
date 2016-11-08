import yaml
from functools import partial

from clients import influxdb_api
import utils
import objects

import logging


logger = logging.getLogger(__name__)


class BaseLMATest(object):
    OKAY_STATUS = 0
    WARNING_STATUS = 1
    UNKNOWN_STATUS = 2
    CRITICAL_STATUS = 3
    DOWN_STATUS = 4

    WARNING_PERCENT = 91
    CRITICAL_PERCENT = 96

    RABBITMQ_DISK_WARNING_PERCENT = 99.99
    RABBITMQ_DISK_CRITICAL_PERCENT = 100
    RABBITMQ_MEMORY_WARNING_VALUE = 1.01
    RABBITMQ_MEMORY_CRITICAL_VALUE = 1.0001

    @classmethod
    def setup_class(cls):
        cls.config = yaml.load(file(utils.get_fixture("config.yaml")))

        nodes = cls.config.get("nodes")
        cls.cluster = objects.Cluster()

        for node_args in nodes:
            cls.cluster.add_host(
                objects.Host(**node_args)
            )

        cls.influxdb_api = influxdb_api.InfluxdbApi(
            address=cls.config["lma"]["influxdb_vip"],
            port=cls.config["lma"]["influxdb_port"],
            username=cls.config["lma"]["influxdb_username"],
            password=cls.config["lma"]["influxdb_password"],
            db_name=cls.config["lma"]["influxdb_db_name"]
        )

    def check_filesystem_alarms(self, node, filesystem, source,
                                filename, node_role, alarm_type="node"):
        check_alarm = partial(self.influxdb_api.check_alarms,
                              alarm_type=alarm_type,
                              filter_value=node_role,
                              source=source,
                              hostname=node.hostname)

        check_alarm(value=self.OKAY_STATUS)

        node.os.fill_up_filesystem(filesystem, self.WARNING_PERCENT, filename)
        logger.info("Checking {}-warning alarm".format(source))
        check_alarm(value=self.WARNING_STATUS)

        node.os.clean_filesystem(filename)
        check_alarm(value=self.OKAY_STATUS)

        node.os.fill_up_filesystem(filesystem, self.CRITICAL_PERCENT, filename)
        logger.info("Checking {}-critical alarm".format(source))
        check_alarm(value=self.CRITICAL_STATUS)

        node.os.clean_filesystem(filename)
        check_alarm(value=self.OKAY_STATUS)

    def check_rabbit_mq_disk_alarms(self, controller, status, percent):
        check_alarm = partial(self.influxdb_api.check_alarms,
                              alarm_type="service",
                              filter_value="rabbitmq-cluster",
                              source="disk",
                              hostname=controller.hostname)
        check_alarm(value=self.OKAY_STATUS)

        default_value = controller.exec_command(
            "rabbitmqctl environment | grep disk_free_limit | "
            "sed -r 's/}.+//' | sed 's|.*,||'")

        cmd = ("rabbitmqctl -n rabbit@messaging-node-3 set_disk_free_limit $"
               "(df | grep /dev/dm- | "
               "awk '{{ printf(\"%.0f\\n\", 1024 * ((($3 + $4) * "
               "{percent} / 100) - $3))}}')")
        controller.exec_command(cmd.format(percent=percent))
        check_alarm(value=status)

        controller.exec_command(
            "rabbitmqctl set_disk_free_limit {}".format(default_value))
        check_alarm(value=self.OKAY_STATUS)

    def check_rabbit_mq_memory_alarms(self, controller, status, value):
        check_alarm = partial(self.influxdb_api.check_alarms,
                              alarm_type="service",
                              filter_value="rabbitmq-cluster",
                              source="memory",
                              hostname=controller.hostname)
        check_alarm(value=self.OKAY_STATUS)

        default_value = controller.exec_command(
            "rabbitmqctl environment | grep disk_free_limit | "
            "sed -r 's/}.+//' | sed 's|.*,||'")
        mem_usage = self.influxdb_api.get_rabbitmq_memory_usage()

        controller.exec_command(
            "rabbitmqctl set_vm_memory_high_watermark absolute \"{memory}\"".
                format(memory=int(mem_usage * value)))
        check_alarm(value=status)

        self.set_rabbitmq_memory_watermark(controller, default_value)
        check_alarm(value=self.OKAY_STATUS)

    def set_rabbitmq_memory_watermark(self, controller, limit, timeout=5 * 60):
        def check_result():
            exit_code = controller.os.transport.exec_sync(
                "rabbitmqctl set_vm_memory_high_watermark {}".format(limit))
            if exit_code == 0:
                return True
            else:
                return False

        msg = "Failed to set vm_memory_high_watermark to {}".format(limit)
        utils.wait(check_result, timeout=timeout, interval=10, timeout_msg=msg)

    def verify_service_alarms(self, trigger_fn, trigger_count,
                              metrics, status):
        for _ in range(trigger_count):
            trigger_fn()
        for service, source in metrics.items():
            self.influxdb_api.check_alarms(
                alarm_type="service",
                filter_value=service,
                source=source,
                hostname=None,
                value=status)
