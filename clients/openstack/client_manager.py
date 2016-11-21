import logging

# Default client libs
from cinderclient import client as cinder_client
from glanceclient import client as glance_client
from heatclient import client as heat_client
from keystoneauth1 import session as keystone_session
from keystoneauth1 import identity as keystone_identity
from keystoneclient import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from novaclient import client as novaclient


LOG = logging.getLogger(__name__)
try:
    import muranoclient.v1.client
except ImportError:
    #LOG.exception()
    LOG.warning('Murano client could not be imported.')
try:
    import saharaclient.client
except ImportError:
    #LOG.exception()
    LOG.warning('Sahara client could not be imported.')
try:
    import ceilometerclient.v2.client
except ImportError:
    # LOG.exception()
    LOG.warning('Ceilometer client could not be imported.')
try:
    import ironicclient
except ImportError:
    # LOG.exception()
    LOG.warning('Ironic client could not be imported')
try:
    import muranoclient.glance.client as art_client
except ImportError:
    # LOG.exception()
    LOG.warning('Artifacts client could not be imported')


class OfficialClientManager(object):
    """Manager that provides access to the official python clients for
    calling various OpenStack APIs.
    """

    CINDERCLIENT_VERSION = 2
    GLANCECLIENT_VERSION = 2
    HEATCLIENT_VERSION = 1
    KEYSTONECLIENT_VERSION = 2, 0
    NEUTRONCLIENT_VERSION = 2
    NOVACLIENT_VERSION = 2

    def __init__(self, username=None, password=None,
                 tenant_name=None, auth_url=None, endpoint_type="publicURL",
                 cert=False, domain="Default", **kwargs):
        self.traceback = ""

        self.client_attr_names = [
            "auth",
            "compute",
            "network",
            "volume",
            "image",
            "orchestration",
        ]
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.project_name = tenant_name
        self.auth_url = auth_url
        self.endpoint_type = endpoint_type
        self.cert = cert
        self.domain = domain
        self.kwargs = kwargs

        # Lazy clients
        self._auth = None
        self._compute = None
        self._network = None
        self._volume = None
        self._image = None
        self._orchestration = None

    @classmethod
    def _get_auth_session(cls, username=None, password=None,
                          tenant_name=None, auth_url=None, cert=None,
                          domain='Default'):
        if None in (username, password, tenant_name):
            print(username, password, tenant_name)
            msg = ("Missing required credentials for identity client. "
                   "username: {username}, password: {password}, "
                   "tenant_name: {tenant_name}").format(
                       username=username,
                       password=password,
                       tenant_name=tenant_name, )
            raise msg

        if cert and "https" not in auth_url:
            auth_url = auth_url.replace("http", "https")

        if cls.KEYSTONECLIENT_VERSION == (2, 0):
            auth_url = "{}{}".format(auth_url, "v2.0/")
            auth = keystone_identity.v2.Password(
                username=username, password=password, auth_url=auth_url,
                tenant_name=tenant_name)
        else:
            auth_url = "{}{}".format(auth_url, "v3/")
            auth = keystone_identity.v3.Password(
                auth_url=auth_url, user_domain_name=domain,
                username=username, password=password,
                project_domain_name=domain, project_name=tenant_name)

        auth_session = keystone_session.Session(auth=auth, verify=cert)
        # auth_session.get_auth_headers()
        return auth_session

    @classmethod
    def get_auth_client(cls, username=None, password=None,
                        tenant_name=None, auth_url=None, cert=None,
                        domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        keystone = keystone_client.Client(
            cls.KEYSTONECLIENT_VERSION, session=session, **kwargs)
        keystone.management_url = auth_url
        return keystone

    @classmethod
    def get_compute_client(cls, username=None, password=None,
                           tenant_name=None, auth_url=None, cert=None,
                           domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        service_type = 'compute'
        compute_client = novaclient.Client(
            version=cls.NOVACLIENT_VERSION, session=session,
            service_type=service_type, no_cache=True, **kwargs)
        return compute_client

    @classmethod
    def get_network_client(cls, username=None, password=None,
                           tenant_name=None, auth_url=None, cert=None,
                           domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        service_type = 'network'
        return neutron_client.Client(
            service_type=service_type, session=session, **kwargs)

    @classmethod
    def get_volume_client(cls, username=None, password=None,
                          tenant_name=None, auth_url=None, cert=None,
                          domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        service_type = 'volume'
        return cinder_client.Client(
            version=cls.CINDERCLIENT_VERSION,
            service_type=service_type,
            session=session, **kwargs)

    @classmethod
    def get_image_client(cls, username=None, password=None,
                         tenant_name=None, auth_url=None, cert=None,
                         domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        service_type = 'image'
        return glance_client.Client(
            version=cls.GLANCECLIENT_VERSION,
            service_type=service_type,
            session=session, **kwargs)

    @classmethod
    def get_orchestration_client(cls, username=None, password=None,
                                 tenant_name=None, auth_url=None, cert=None,
                                 domain='Default', **kwargs):
        session = cls._get_auth_session(
            username=username, password=password, tenant_name=tenant_name,
            auth_url=auth_url, cert=cert, domain=domain)
        service_type = 'orchestration'
        print(cls.HEATCLIENT_VERSION)
        return heat_client.Client(
            version=cls.HEATCLIENT_VERSION,
            service_type=service_type,
            session=session, **kwargs)

    @property
    def auth(self):
        if self._auth is None:
            self._auth = self.get_auth_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain, endpoint_type=self.endpoint_type
            )
        return self._auth

    @property
    def compute(self):
        if self._compute is None:
            self._compute = self.get_compute_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain, endpoint_type=self.endpoint_type
            )
        return self._compute

    @property
    def network(self):
        if self._network is None:
            self._network = self.get_network_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain, endpoint_type=self.endpoint_type
            )
        return self._network

    @property
    def volume(self):
        if self._volume is None:
            self._volume = self.get_volume_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain, endpoint_type=self.endpoint_type
            )
        return self._volume

    @property
    def image(self):
        if self._image is None:
            self._image = self.get_image_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain
            )
        return self._image

    @property
    def orchestration(self):
        if self._orchestration is None:
            self._orchestration = self.get_orchestration_client(
                self.username, self.password, self.tenant_name, self.auth_url,
                self.cert, self.domain, endpoint_type=self.endpoint_type
            )
        return self._orchestration
