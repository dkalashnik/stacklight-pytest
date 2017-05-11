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
    RABBITMQ_MEMORY_CRITICAL_VALUE = 0.9

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

        influxdb_config = cls.config.get("influxdb")
        cls.influxdb_api = influxdb_grafana_api.InfluxdbApi(
            address=influxdb_config["influxdb_vip"],
            port=influxdb_config["influxdb_port"],
            username=influxdb_config["influxdb_username"],
            password=influxdb_config["influxdb_password"],
            db_name=influxdb_config["influxdb_db_name"]
        )

        grafana_config = cls.config.get("grafana")
        cls.grafana_api = influxdb_grafana_api.GrafanaApi(
            address=grafana_config["grafana_vip"],
            port=grafana_config["grafana_port"],
            username=grafana_config["grafana_username"],
            password=grafana_config["grafana_password"],
            influxdb=cls.influxdb_api,
        )

        elasticsearch_config = cls.config.get("elasticsearch")
        cls.elasticsearch_api = es_kibana_api.ElasticSearchApi(
            host=elasticsearch_config["elasticsearch_vip"],
            port=elasticsearch_config["elasticsearch_port"],
        )

        nagios_config = cls.config.get("nagios")
        cls.nagios_api = nagios_api.NagiosApi(
            address=nagios_config["nagios_vip"],
            port=nagios_config["nagios_port"],
            username=nagios_config["nagios_username"],
            password=nagios_config["nagios_password"],
            tls_enabled=nagios_config["nagios_tls"],
        )

        cls.kibana_api = es_kibana_api.KibanaApi(
            host=elasticsearch_config["elasticsearch_vip"],
            port=elasticsearch_config["kibana_port"],
        )

        auth = cls.config.get("keystone")
        public_vip = auth["public_address"]
        auth_url = "http://{}:5000/".format(public_vip)

        cls.os_clients = os_clients.OfficialClientManager(
            username=auth["admin_name"],
            password=auth["admin_password"],
            tenant_name=auth["admin_tenant"],
            auth_url=auth_url,
            cert=False,
            domain=auth.get("domain", "Default"),
        )

    def get_generic_alarm_checker(self, node, source):
        def check_alarm(value):
            return self.influxdb_api.check_mk_alarm(
                member=source, warning_level=value, hostname=node.hostname)
        return check_alarm

    def check_service_installed(self, name, role=None):
        """Checks that service is installed on nodes with provided role."""
        if role is None:
            role = "monitoring"
        nodes = self.cluster.filter_by_role(role)
        for node in nodes:
            node.os.check_package_installed(name)

    def check_service_running(self, name, role=None):
        """Checks that service is running on nodes with provided role."""
        if role is None:
            role = "monitoring"
        nodes = self.cluster.filter_by_role(role)
        for node in nodes:
            node.os.manage_service(name, "status")
