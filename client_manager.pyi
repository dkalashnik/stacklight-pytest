import novaclient.client
import novaclient.v2.client
class OfficialClientManager(object):
    def _get_compute_client(self,
                            username:str=None,
                            password:str=None,
                            tenant_name:str=None,
                            identity_url:str=None)-> novaclient.v2.client.Client: ...
