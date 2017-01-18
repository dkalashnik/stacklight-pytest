import urlparse

from stacklight_tests import utils


check_http_get_response = utils.check_http_get_response


class NagiosApi(object):
    pages = {
        "Services": "status.cgi?host=all&limit=0",
        "Hosts": "status.cgi?hostgroup=all&style=hostdetail&limit=0"
    }

    def __init__(self, address, port, username, password, tls_enabled=True):
        super(NagiosApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.scheme = "https" if tls_enabled else "http"
        self.nagios_url = (
            "{scheme}://{user}:{password}@{address}:{port}"
            "/cgi-bin/nagios3/".format(
                scheme=self.scheme,
                user=self.username, password=self.password,
                address=self.address, port=self.port))

    def get_page(self, page_name, expected_codes=(200,)):
        url = urlparse.urljoin(self.nagios_url, self.pages[page_name])
        response = utils.check_http_get_response(
            url=url, expected_codes=expected_codes)
        return response.text
