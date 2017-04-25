import logging

from stacklight_tests.clients.prometheus import prometheus_client
from stacklight_tests import objects
from stacklight_tests import utils

logger = logging.getLogger(__name__)


class BaseLMAPrometheusTest(object):
    @classmethod
    def setup_class(cls):
        cls.config = utils.load_config()
        nodes = cls.config.get("ssh")
        cls.cluster = objects.Cluster()

        for node_args in nodes:
            cls.cluster.add_host(
                objects.Host(**node_args)
            )

        prometheus_config = cls.config.get("prometheus")
        cls.prometheus_api = prometheus_client.PrometheusClient(
            "http://{0}:{1}/".format(
                prometheus_config["prometheus_vip"],
                prometheus_config["prometheus_server_port"])
        )
