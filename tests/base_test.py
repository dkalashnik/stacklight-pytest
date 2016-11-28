from functools import partial
import logging

import yaml

from clients import es_kibana_api
from clients import influxdb_grafana_api
from clients.openstack import client_manager as os_clients
import objects
import utils


logger = logging.getLogger(__name__)


class BaseLMATest(os_clients.OSCliActionsMixin):
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

        lma = cls.config.get("lma")
        cls.influxdb_api = influxdb_grafana_api.InfluxdbApi(
            address=lma["influxdb_vip"],
            port=lma["influxdb_port"],
            username=lma["influxdb_username"],
            password=lma["influxdb_password"],
            db_name=lma["influxdb_db_name"]
        )

        cls.grafana_api = influxdb_grafana_api.GrafanaApi(
            address=lma["grafana_vip"],
            port=lma["grafana_port"],
            username=lma["grafana_username"],
            password=lma["grafana_password"],
        )

        cls.es_kibana_api = es_kibana_api.EsKibanaApi(
            host=lma["elasticsearch_vip"],
            port=lma["elasticsearch_port"],
        )

        # NOTE(rpromyshlennikov): It may need refactor,
        # if we use deploy without SSL
        auth = cls.config.get("auth")
        cert_content = auth["public_ssl"]["cert_data"]["content"]
        cert = utils.write_cert(cert_content) if cert_content else False
        public_vip = auth["public_vip"]
        auth_url = "http://{}:5000/".format(public_vip)
        if cert:
            hostname = auth["public_ssl"]["hostname"]
            auth_url = "https://{}:5000/".format(hostname)
        cls.os_clients = os_clients.OfficialClientManager(
            username=auth["access"]["user"],
            password=auth["access"]["password"],
            tenant_name=auth["access"]["tenant"],
            auth_url=auth_url,
            cert=cert,
            domain=auth["access"].get("domain", "Default"),
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

        default_value = controller.exec_command( # DISK_FREE_LIMIT? o_O
            "rabbitmqctl -n rabbit@messaging-node-3 environment | grep disk_free_limit | "
            "sed -r 's/}.+//' | sed 's|.*,||'")
        mem_usage = self.influxdb_api.get_rabbitmq_memory_usage()

        cmd = "rabbitmqctl -n rabbit@messaging-node-3 set_vm_memory_high_watermark absolute \"{memory}\"".format(memory=int(mem_usage * value))
        print(cmd)
        controller.exec_command(cmd)
        check_alarm(value=status)

        self.set_rabbitmq_memory_watermark(controller, '0.4')
        check_alarm(value=self.OKAY_STATUS)

    def set_rabbitmq_memory_watermark(self, controller, limit, timeout=5 * 60):
        def check_result():
            exit_code, _, _ = controller.os.transport.exec_sync(
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
        print('check metric {0}'.format(metrics.items()))
        print('status: {0}'.format(status))
        for service, source in metrics.items():
            self.influxdb_api.check_alarms(
                alarm_type="service",
                filter_value=service,
                source=source,
                hostname=None,
                value=status)

