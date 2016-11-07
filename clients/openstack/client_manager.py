import novaclient.client
import novaclient.v2.client

import logging
LOG = logging.getLogger(__name__)
# Default client libs
try:
    import heatclient.v1.client
except Exception:
    #LOG.exception()
    LOG.warning('Heatclient could not be imported.')
try:
    import muranoclient.v1.client
except Exception:
    #LOG.exception()
    LOG.warning('Muranoclient could not be imported.')
try:
    import saharaclient.client
except Exception:
    #LOG.exception()
    LOG.warning('Sahara client could not be imported.')
try:
    import ceilometerclient.v2.client
except Exception:
    # LOG.exception()
    LOG.warning('Ceilometer client could not be imported.')
try:
    import neutronclient.neutron.client
except Exception:
    # LOG.exception()
    LOG.warning('Neutron client could not be imported.')
try:
    import glanceclient
except Exception:
    # LOG.exception()
    LOG.warning('Glance client could not be imported')
try:
    import ironicclient
except Exception:
    # LOG.exception()
    LOG.warning('Ironic client could not be imported')
try:
    import muranoclient.glance.client as art_client
except Exception:
    # LOG.exception()
    LOG.warning('Artifacts client could not be imported')


class OfficialClientManager(object):
    """Manager that provides access to the official python clients for
    calling various OpenStack APIs.
    """

    NOVACLIENT_VERSION = '2'
    CINDERCLIENT_VERSION = '2'

    def __init__(self):
        self.traceback = ''

        self.client_attr_names = [
            'compute_client'
        ]

    def get_compute_client(self,
                           username=None,
                           password=None,
                           tenant_name=None,
                           identity_url=None):
        if None in (username, password, tenant_name):
            print(username, password, tenant_name)
            msg = ("Missing required credentials for identity client. "
                   "username: {username}, password: {password}, "
                   "tenant_name: {tenant_name}").format(
                       username=username,
                       password=password,
                       tenant_name=tenant_name, )
            raise msg

        client_args = (username, password, tenant_name, identity_url)

        service_type = 'compute'
        print(self.NOVACLIENT_VERSION)
        return novaclient.client.Client(self.NOVACLIENT_VERSION,
                                        *client_args,
                                        service_type=service_type,
                                        no_cache=True,
                                        insecure=True,
                                        endpoint_type='publicURL')
