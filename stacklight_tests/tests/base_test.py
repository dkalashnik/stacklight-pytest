from functools import partial
import logging

from stacklight_tests.clients import es_kibana_api
from stacklight_tests.clients import influxdb_grafana_api
from stacklight_tests.clients import nagios_api
from stacklight_tests.clients.openstack import client_manager as os_clients
from stacklight_tests import objects
from stacklight_tests import utils

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
    RABBITMQ_MEMORY_WARNING_VALUE = 1.1
    RABBITMQ_MEMORY_CRITICAL_VALUE = 1.0

    @classmethod
    def setup_class(cls):
        cls.config = utils.load_config()
        # TODO(rpromyshlennikov): make types as enum?
        cls.env_type = cls.config.get("env", {}).get("type", "")
        cls.is_mk = cls.env_type == 'mk'

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
            influxdb=cls.influxdb_api,
        )

        cls.es_kibana_api = es_kibana_api.EsKibanaApi(
            host=lma["elasticsearch_vip"],
            port=lma["elasticsearch_port"],
        )

        cls.nagios_api = nagios_api.NagiosApi(
            address=lma["nagios_vip"],
            port=lma["nagios_port"],
            username=lma["nagios_username"],
            password=lma["nagios_password"],
            tls_enabled=lma["nagios_tls"],
        )

        # NOTE(rpromyshlennikov): It may need refactor,
        # if we use deploy without SSL
        auth = cls.config.get("auth")
        public_vip = auth["public_vip"]
        auth_url = "http://{}:5000/".format(public_vip)

        cert = False

        if auth.get("public_ssl", None) is not None:
            cert_content = auth["public_ssl"]["cert_data"]["content"]
            cert = utils.write_cert(cert_content) if cert_content else False
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

    def setup_method(self):
        self.destructive_actions = []

    def teardown_method(self):
        for recovery_method in self.destructive_actions:
            try:
                recovery_method()
            except Exception as e:
                logger.error("Recovery failed: {} with exception: {}".format(
                    recovery_method, e))

    def get_generic_alarm_checker(self, node, source, node_role,
                                  alarm_type="node"):
        if not self.is_mk:
            check_alarm = partial(self.influxdb_api.check_alarms,
                                  alarm_type=alarm_type,
                                  filter_value=node_role,
                                  source=source,
                                  hostname=node.hostname)
        else:
            def check_alarm(value):
                return self.influxdb_api.check_mk_alarm(
                    member=source, warning_level=value, hostname=node.hostname)
        return check_alarm

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
