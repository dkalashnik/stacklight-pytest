from stacklight_tests.clients import http_client


class BlackBoxExporterClient(http_client.HttpClient):
    def get_probe(self, target, module="http_2xx"):

        params = {
            "module": module,
            "target": target
        }

        _, result = self.get("/probe", params=params)

        return result.splitlines()
