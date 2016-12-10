import json
from random import choice

import fuelclient
from fuelclient import client as api_client
import yaml

from stacklight_tests.clients.system import general_client
from stacklight_tests import settings
from stacklight_tests import utils


class FuelConfig(object):
    def __init__(self, fuel_address, fuel_username, fuel_password):
        master_ssh = general_client.GeneralActionsClient(
            fuel_address, fuel_username, password=fuel_password)

        self.put_updated_hiera(master_ssh)
        fuel_access = self.get_hiera_value(master_ssh, "FUEL_ACCESS")

        self.api_connection = api_client.Client(
            host=fuel_address,
            port=8000,
            os_username=fuel_access["user"],
            os_password=fuel_access["password"],
            os_tenant_name="admin")

        nailgun_nodes_client = fuelclient.get_client(
            'node', connection=self.api_connection)

        nailgun_nodes = nailgun_nodes_client.get_all()
        private_key = master_ssh.get_file_content("/root/.ssh/id_rsa")

        self.nodes = []
        for nailgun_node in nailgun_nodes:
            node = {
                "address": nailgun_node["ip"],
                "hostname": nailgun_node["fqdn"],
                "username": "root",
                "private_key": private_key,
                "roles": nailgun_node["roles"]
            }
            self.nodes.append(node)

    def put_updated_hiera(self, ssh):
        ssh.put_file(utils.get_fixture("hiera"), "/tmp/hiera")
        ssh.exec_command("chmod +x /tmp/hiera")

    def get_hiera_value(self, ssh, value):
        return json.loads(ssh.exec_command(
            "/tmp/hiera --format json {0}".format(value)))

    def get_openstack_credentials(self):
        controller = choice([node for node in self.nodes
                            if "controller" in node["roles"]])
        controller_ssh = general_client.GeneralActionsClient(
            address=controller["address"],
            username=controller["username"],
            private_key=controller["private_key"])

        self.put_updated_hiera(controller_ssh)

        openstack_auth_config = {
            "access":
                self.get_hiera_value(controller_ssh, "access"),
            "management_vip":
                self.get_hiera_value(controller_ssh, "management_vip"),
            "public_vip":
                self.get_hiera_value(controller_ssh, "public_vip"),
            "public_ssl":
                self.get_hiera_value(controller_ssh, "public_ssl"),
        }
        return openstack_auth_config

    def get_lma_credentials(self):
        def clean_password(password):
            return password.replace("\n", "")

        monitoring = choice([node for node in self.nodes
                             if "elasticsearch_kibana" in node["roles"]])

        monitoring_ssh = general_client.GeneralActionsClient(
            address=monitoring["address"],
            username=monitoring["username"],
            private_key=monitoring["private_key"])

        self.put_updated_hiera(monitoring_ssh)

        lma_config = {
            "influxdb_vip":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::vip"),
            "influxdb_port":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::influxdb_port"),
            "influxdb_username":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::admin_username"),
            "influxdb_password":
                clean_password(self.get_hiera_value(
                    monitoring_ssh, "lma::influxdb::admin_password")),
            "influxdb_db_name": self.get_hiera_value(monitoring_ssh,
                                                     "lma::influxdb::dbname"),
            "elasticsearch_vip":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::elasticsearch::vip"),
            "elasticsearch_port":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::elasticsearch::rest_port"),
            "grafana_vip":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::grafana::vip"),
            "grafana_port":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::grafana_frontend_port"),
            "grafana_username":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::grafana::mysql::admin_username"),
            "grafana_password":
                clean_password(self.get_hiera_value(
                    monitoring_ssh, "lma::grafana::mysql::admin_password")),

        }
        return lma_config

    def main(self):
        config = {
            "env": {"type": "fuel"},
            "nodes": self.nodes,
            "lma": self.get_lma_credentials(),
            "auth": self.get_openstack_credentials(),
        }

        config_filename = utils.get_fixture("config.yaml",
                                            check_existence=False)
        with file(config_filename, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)


if __name__ == '__main__':
    FuelConfig(settings.ENV_FUEL_IP,
               settings.ENV_FUEL_LOGIN,
               settings.ENV_FUEL_PASSWORD).main()
