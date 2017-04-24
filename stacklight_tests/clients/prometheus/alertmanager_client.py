import json

from stacklight_tests.clients import http_client


class AlertManagerClient(http_client.HttpClient):
    def get_status(self):
        _, resp = self.get("/api/v1/status")
        status = json.loads(resp)
        return status["data"]

    def list_alert_groups(self):
        _, resp = self.get("/api/v1/alerts/groups")
        status = json.loads(resp)
        return status["data"]

    def list_alerts(self):
        _, resp = self.get("/api/v1/alerts")
        status = json.loads(resp)
        return status["data"]

    # def add_alert(self):
    #     return self.post("/api/v1/alerts")

    def list_silences(self):
        _, resp = self.get("/api/v1/silences")
        status = json.loads(resp)
        return status["data"]

    # def add_silence(self):
    #     return self.post("/api/v1/silences")

    def get_silence(self, silence_id):
        return self.get("/api/v1/silence/{}".format(silence_id))

    def delete_silence(self, silence_id):
        return self.delete("/api/v1/silence/{}".format(silence_id))
