import yaml

import utils
import objects
from clients import influxdb_api


class BaseLMATest(object):
    @classmethod
    def setup_class(cls):
        cls.config = yaml.load(file(utils.get_fixture("config.yaml")))

        transport_driver = cls.config.get("transport_driver")
        nodes = cls.config.get("nodes")
        cls.cluster = objects.Cluster()

        for node_args in nodes:
            cls.cluster.add_host(
                objects.Host(transport_driver=transport_driver,
                             **node_args)
            )

        cls.influxdb_api = influxdb_api.InfluxdbApi()
