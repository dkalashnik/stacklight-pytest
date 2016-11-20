import logging
import time

from tests import base_test


logger = logging.getLogger(__name__)


class TestOpenStackClients(base_test.BaseLMATest):
    def test_check_os_conn(self):
        from clients.openstack import client_manager
        manager = client_manager.OfficialClientManager
        nonpos_args = dict(
            domain='Default',
            username='admin',
            password='admin',
            tenant_name='admin',
            cert=False,
            # cert="/home/user/stacklight-integration-tests/ca.my.pem",
            auth_url='https://10.109.8.8:5000/'
            # auth_url='http://public.fuel.local:5000/'
        )
        session = manager._get_auth_session(**nonpos_args)
        nonpos_args.update(endpoint_type='adminURL')
        auth = manager.get_auth_client(**nonpos_args)
        print auth.users.list()
        compute = manager.get_compute_client(**nonpos_args)
        print compute.servers.list()
        network = manager.get_network_client(**nonpos_args)
        print network.list_networks()
        volumes = manager.get_volume_client(**nonpos_args)
        print volumes.volumes.list()
        orchestr = manager.get_orchestration_client(**nonpos_args)
        print list(orchestr.stacks.list())
        nonpos_args.pop("endpoint_type")
        images = manager.get_image_client(**nonpos_args)
        print list(images.images.list())

        ################## Auto client test ####################

        # session = manager._get_auth_session(**nonpos_args)
        print self.os_clients.auth.users.list()
        print self.os_clients.compute.servers.list()
        print self.os_clients.network.list_networks()
        print self.os_clients.volume.volumes.list()
        print list(self.os_clients.orchestration.stacks.list())
        print list(self.os_clients.image.images.list())
