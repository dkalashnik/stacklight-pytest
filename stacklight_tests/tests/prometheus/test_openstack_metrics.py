import logging

from stacklight_tests import utils
from stacklight_tests.tests.test_functional import wait_for_resource_status

logger = logging.getLogger(__name__)


class TestOpenstackMetrics(object):
    def check_openstack_metrics(self, prometheus_api, query, value, msg):
        def _verify_notifications(q, v):
            output = prometheus_api.get_query(q)
            logger.info("Check {} in {}".format(v, output))
            return v in output[0]["value"]
        utils.wait(
            lambda: _verify_notifications(query, str(value)),
            interval=10, timeout=2 * 60, timeout_msg=msg
        )

    def test_glance_metrics(self, destructive, prometheus_api, os_clients):
        image_name = utils.rand_name("image-")
        client = os_clients.image
        image = client.images.create(
            name=image_name,
            container_format="bare",
            disk_format="raw",
            visibility="public")
        client.images.upload(image.id, "dummy_data")
        wait_for_resource_status(client.images, image.id, "active")
        destructive.append(lambda: client.images.delete(image.id))

        images_count = len([im for im in client.images.list()])
        images_size = sum([im["size"] for im in client.images.list()])

        count_query = ('{__name__="openstack_glance_images",'
                       'visibility="public",status="active"}')
        err_count_msg = "Incorrect image count in metric {}".format(
            count_query)
        self.check_openstack_metrics(
            prometheus_api, count_query, images_count, err_count_msg)

        size_query = ('{__name__="openstack_glance_images_size",'
                      'visibility="public", status="active"}')
        error_size_msg = "Incorrect image size in metric {}".format(size_query)
        self.check_openstack_metrics(
            prometheus_api, size_query, images_size, error_size_msg)

        client.images.delete(image.id)
        utils.wait(
            lambda: (image.id not in [i["id"] for i in client.images.list()])
        )

    def test_keystone_metrics(self, prometheus_api, os_clients):
        client = os_clients.auth
        tenants = client.tenants.list()
        users = client.users.list()

        metric_dict = {
            '{__name__="openstack_keystone_tenants_total"}':
                [len(tenants), "Incorrect tenant count in metric {}"],
            'openstack_keystone_tenants{state="enabled"}':
                [len(filter(lambda x: x.enabled, tenants)),
                 "Incorrect enabled tenant count in metric {}"],
            'openstack_keystone_tenants{state="disabled"}':
                [len(filter(lambda x: not x.enabled, tenants)),
                 "Incorrect disabled tenant count in metric {}"],
            '{__name__="openstack_keystone_roles_roles"}':
                [len(client.roles.list()),
                 "Incorrect roles count in metric {}"],
            '{__name__="openstack_keystone_users_total"}':
                [len(users), "Incorrect user count in metric {}"],
            'openstack_keystone_users{state="enabled"}':
                [len(filter(lambda x: x.enabled, users)),
                 "Incorrect enabled user count in metric {}"],
            'openstack_keystone_users{state="disabled"}':
                [len(filter(lambda x: not x.enabled, users)),
                 "Incorrect disabled user count in metric {}"]
        }

        for metric in metric_dict.keys():
            self.check_openstack_metrics(
                prometheus_api, metric, metric_dict[metric][0],
                metric_dict[metric][1].format(metric))

    def test_neutron_metrics(self, prometheus_api, os_clients):
        client = os_clients.network

        metric_dict = {
            '{__name__="openstack_neutron_networks_total"}':
                [len(client.list_networks()["networks"]),
                 "Incorrect net count in metric {}"],
            '{__name__="openstack_neutron_subnets_total"}':
                [len(client.list_subnets()["subnets"]),
                 "Incorrect subnet count in metric {}"],
            '{__name__="openstack_neutron_floatingips_total"}':
                [len(client.list_floatingips()["floatingips"]),
                 "Incorrect floating ip count in metric {}"],
            '{__name__="openstack_neutron_routers_total"}':
                [len(client.list_routers()["routers"]),
                 "Incorrect router count in metric {}"],
            'openstack_neutron_routers{state="active"}':
                [len(filter(lambda x: x["status"] == "ACTIVE",
                            client.list_routers()["routers"])),
                 "Incorrect active router count in metric {}"],
            '{__name__="openstack_neutron_ports_total"}':
                [len(client.list_ports()["ports"]),
                 "Incorrect port count in metric {}"]
        }

        for metric in metric_dict.keys():
            self.check_openstack_metrics(
                prometheus_api, metric, metric_dict[metric][0],
                metric_dict[metric][1].format(metric))

    def test_cinder_metrics(self, destructive, prometheus_api, os_clients):
        volume_name = utils.rand_name("volume-")
        client = os_clients.volume
        volume = client.volumes.create(size=1, name=volume_name)
        wait_for_resource_status(client.volumes, volume.id, "error")
        destructive.append(lambda: client.volume.delete(volume))

        volumes_count = len([vol for vol in client.volumes.list()])
        volumes_size = sum([vol.size for vol in client.volumes.list()]) * 10**9

        count_query = ('{__name__="openstack_cinder_volumes",'
                       'status="error"}')
        err_count_msg = "Incorrect volume count in metric {}".format(
            count_query)
        self.check_openstack_metrics(
            prometheus_api, count_query, volumes_count, err_count_msg)

        size_query = ('{__name__="openstack_cinder_volumes_size",'
                      'status="error"}')
        error_size_msg = "Incorrect volume size in metric {}".format(
            size_query)
        self.check_openstack_metrics(
            prometheus_api, size_query, volumes_size, error_size_msg)

        client.volumes.delete(volume)
        utils.wait(
            lambda: (volume.id not in [v.id for v in client.volumes.list()])
        )

    def test_nova_telegraf_metrics(self, prometheus_api, os_clients):
        client = os_clients.compute

        def get_servers_count(st):
            return len(filter(
                lambda x: x.status == st, client.servers.list()))

        err_msg = "Incorrect servers count in metric {}"
        for status in ["active", "error"]:
            q1 = '{' + '__name__="openstack_nova_instances_{}"'.format(
                status) + '}'
            q2 = 'openstack_nova_{}'.format(status)
            q3 = 'openstack_nova_instances{' + 'state="{}"'.format(
                status) + '}'
            self.check_openstack_metrics(
                prometheus_api, q1, get_servers_count(status.upper()),
                err_msg.format(q1))
            self.check_openstack_metrics(
                prometheus_api, q2, get_servers_count(status.upper()),
                err_msg.format(q2))
            self.check_openstack_metrics(
                prometheus_api, q3, get_servers_count(status.upper()),
                err_msg.format(q3))

    def test_nova_services_metrics(self, prometheus_api, cluster):
        controllers = filter(lambda x: "controller" in x.roles, cluster.hosts)
        computes = filter(lambda x: "compute" in x.roles, cluster.hosts)
        controller_services = ["nova-cert", "nova-conductor",
                               "nova-consoleauth", "nova-scheduler"]
        compute_services = ["nova-compute"]
        err_service_msg = "Service {} is down on the {} node"
        for controller in controllers:
            for service in controller_services:
                q = 'hostname="{}",service="{}"'.format(
                    controller.hostname, service)
                self.check_openstack_metrics(
                    prometheus_api,
                    'openstack_nova_service{' + q + ',state="up"}',
                    0, err_service_msg.format(service, controller.hostname))
        for compute in computes:
            for service in compute_services:
                q = 'hostname="{}",service="{}"'.format(
                    compute.hostname, service)
                self.check_openstack_metrics(
                    prometheus_api,
                    'openstack_nova_service{' + q + ',state="up"}',
                    0, err_service_msg.format(service, compute.hostname))
