import yaml

import utils
import objects


class BaseLMATest(object):
    @classmethod
    def setup_class(cls):
        cls.config = yaml.load(file(utils.get_fixture("config.yaml")))

        nodes = cls.config.get("nodes")
        cls.cluster = objects.Cluster()

        for node_args in nodes:
            cls.cluster.add_host(
                objects.Host(**node_args)
            )

