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

    def get_compute_client(self,
                           username=None,
                           password=None,
                           tenant_name=None,
                           identity_url=None):
        client_args = (username, password, tenant_name, identity_url)

        service_type = 'compute'
        print(self.NOVACLIENT_VERSION)
        return novaclient.client.Client(self.NOVACLIENT_VERSION,
                                        *client_args,
                                        service_type=service_type,
                                        no_cache=True,
                                        insecure=True,
                                        endpoint_type='publicURL')

    def get_neutron_client(self,
                           username=None,
                           password=None,
                           tenant_name=None,
                           identity_url=None):
        service_type = 'network'
        import neutronclient.neutron.client
        return neutronclient.neutron.client.Client(
            '2.0',
            username=username,
            password=password,
            tenant_name=tenant_name,
            identity_url=identity_url,
            auth_url=identity_url,
            service_type=service_type,
            no_cache=True,
            insecure=True,
            endpoint_type='publicURL')

    def get_identity_client(self,
                            username=None,
                            password=None,
                            tenant_name=None,
                            auth_url=None,
                            version=None):
        import keystoneclient

        if not version or version == 2:
            return keystoneclient.v2_0.client.Client(username=username,
                                                     password=password,
                                                     tenant_name=tenant_name,
                                                     auth_url=auth_url,
                                                     insecure=True)
        elif version == 3:
            helper_list = auth_url.rstrip("/").split("/")
            helper_list[-1] = "v3/"
            auth_url = "/".join(helper_list)

            return keystoneclient.v3.client.Client(username=username,
                                                   password=password,
                                                   project_name=tenant_name,
                                                   auth_url=auth_url,
                                                   insecure=True)
        else:
            LOG.warning("Version:{0} for keystoneclient is not "
                        "supported with OSTF".format(version))


    def get_glance_client(self,
                          username=None,
                          password=None,
                          tenant_name=None,
                          identity_url=None):
        import glanceclient
        keystone = self.get_identity_client(
            username, password, tenant_name, identity_url)

        endpoint = keystone.service_catalog.url_for(
            service_type='image',
            endpoint_type='publicURL')

        return glanceclient.client.Client(2, endpoint=endpoint,
                                   token=keystone.auth_token,
                                   insecure=True)

    def get_volume_client(self,
                          username=None,
                          password=None,
                          tenant_name=None,
                          identity_url=None
                          ):
        import glanceclient
        keystone = self.get_identity_client(
            username, password, tenant_name, identity_url)

        endpoint = keystone.service_catalog.url_for(
            service_type='image',
            endpoint_type='publicURL')

        return glanceclient.client.Client(2, endpoint=endpoint,
                                          token=keystone.auth_token,
                                          insecure=True)
