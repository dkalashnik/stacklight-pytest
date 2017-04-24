import json

from stacklight_tests.clients import http_client


class PrometheusClient(http_client.HttpClient):
    def get_query(self, query, timestamp=None):
        params = {
            "query": query
        }

        if timestamp is not None:
            params.update({"time": timestamp})

        _, resp = self.get("/api/v1/query", params=params)

        query_result = json.loads(resp)
        if query_result["status"] != "success":
            raise Exception("Failed resp: {}".format(resp))

        if query_result["data"]["resultType"] == "vector":
            return query_result["data"]["result"]

    def get_query_range(self, query, start_time, end_time, step):
        params = {
            "query": query,
            "start": start_time,
            "end": end_time,
            "step": step,
        }

        # TODO: Add proper return
        return self.get("/api/v1/query_range", params=params)

    def get_series(self, match):
        if issubclass(list, match):
            match = [match]

        params = {
            "match[]": match
        }

        # TODO: Add proper return
        return self.get("/api/v1/series", params=params)

    def get_label_values(self, label_name):

        # TODO: Add proper return
        return self.get("/api/v1/label/{}/values".format(label_name))

    def delete_series(self, match):
        if issubclass(list, match):
            match = [match]

        params = {
            "match[]": match
        }

        self.delete("/api/v1/series", params=params)

    def get_targets(self):
        _, resp = self.get("/api/v1/targets")

        targets = json.loads(resp)
        return targets["data"]["activeTargets"]

    def get_alertmanagers(self):
        _, resp = self.get("/api/v1/alertmanagers")

        alertmanagers = json.loads(resp)
        return alertmanagers["data"]["activeAlertmanagers"]