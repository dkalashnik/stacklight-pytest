import subprocess

import yaml

from stacklight_tests import settings
from stacklight_tests import utils


class MKConfig(object):
    def __init__(self, cluster_name="mk22-stacklight-basic"):
        inventory = subprocess.Popen("reclass --inventory",
                                     shell=True,
                                     stdout=subprocess.PIPE).stdout.read()
        inventory = yaml.load(inventory)
        self.nodes = {k: v for k, v in inventory["nodes"].items()
                      if cluster_name in k}

    def check_class(self, class_name, node):
        return any([class_name in c for c in node["classes"]])

    def get_roles(self, node):
        roles_mapping = {
            "openstack.control": "controller",
            "openstack.compute": "compute",
            "stacklight.server": "monitoring",
            "galera.master": "galera.master",
            "galera.slave": "galera.slave",

        }
        roles = [role for role_name, role in roles_mapping.items()
                 if self.check_class(role_name, node)]

        return roles or ["not defined"]

    def generate_nodes(self):
        nodes_config = []
        private_key = open("/root/.ssh/id_rsa").read()

        for node in self.nodes.values():
            node_params = node["parameters"]
            nodes_config.append({
                "address": node_params['_param']['cluster_local_address'],
                "hostname": node_params['linux']['network']['fqdn'],
                "username": "root",
                "private_key": private_key,
                "roles": self.get_roles(node)
            })

        return nodes_config

    def generate_lma(self):
        monitoring_node = filter(
            lambda x: self.check_class("stacklight.server", x),
            self.nodes.values()
        )[0]
        mon_params = monitoring_node['parameters']['_param']

        lma_config = {
            "influxdb_vip": mon_params['grafana_influxdb_host'],
            "influxdb_port": mon_params['influxdb_port'],
            "influxdb_username": mon_params['influxdb_user'],
            "influxdb_password": mon_params['influxdb_password'],
            "influxdb_db_name": mon_params['influxdb_database'],
            "elasticsearch_vip": mon_params['kibana_elasticsearch_host'],
            "elasticsearch_port": mon_params['elasticsearch_port'],
            "grafana_vip": mon_params['grafana_influxdb_host'],
            "grafana_port": mon_params['grafana_port'],
            "grafana_username": mon_params['grafana_user'],
            "grafana_password": mon_params['grafana_password'],
            "nagios_vip": mon_params['nagios_host'],
            "nagios_port": 80,
            "nagios_tls": False,
            "nagios_username": mon_params['nagios_username'],
            "nagios_password": mon_params['nagios_password'],
        }
        return lma_config

    def generate_openstack(self):
        controller_node = filter(
            lambda x: self.check_class("openstack.control", x),
            self.nodes.values()
        )[0]
        ctl_params = controller_node['parameters']
        auth_params = ctl_params['keystone']

        openstack_auth_config = {
            "access": {
                "user": auth_params['server']['admin_name'],
                "password": auth_params['server']['admin_password'],
                "tenant": auth_params['server']['admin_tenant'],
            },

            "management_vip": auth_params['server']['bind']['private_address'],
            "public_vip": auth_params['server']['bind']['public_address'],
            "mysql_user": ctl_params['_param']['mysql_admin_user'],
            "mysql_password": ctl_params['_param']['mysql_admin_password']
        }

        return openstack_auth_config

    def main(self):
        config = {
            "env": {"type": "mk"},
            "nodes": self.generate_nodes(),
            "lma": self.generate_lma(),
            "auth": self.generate_openstack(),
        }

        config_filename = utils.get_fixture("config.yaml",
                                            check_existence=False)
        with file(config_filename, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)


def main():
    MKConfig(cluster_name=settings.ENV_CLUSTER_NAME).main()


if __name__ == '__main__':
    main()
