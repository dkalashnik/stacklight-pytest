import json
import re

from stacklight_tests.clients import http_client


class PrometheusClient(http_client.HttpClient):
    measurements = None

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
        _, resp = self.get("/api/v1/label/{}/values".format(label_name))
        query_result = json.loads(resp)
        if query_result["status"] != "success":
            raise Exception("Failed resp: {}".format(resp))
        return query_result["data"]

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

    def _do_label_values_query(self, query):
        query = query[13:-1]
        # NOTE(rpromyshlennikov): strip "label_values(<metric> or <expr>)".
        if "," in query:
            query, item = [i.strip() for i in query.split(",")]
            return list(
                {res['metric'][item] for res in self.get_query(query)})
        return self.get_label_values(query)

    def _do_query_result_query(self, query, regex=None):
        def convert_to_human_readable_string(metric):
            metric_string = metric["__name__"] + "{"
            items = ['{}="{}"'.format(name, value)
                     for name, value in metric.items()
                     if name != "__name__"]
            metric_string += ",".join(items)
            return metric_string + "}"
        # NOTE(rpromyshlennikov): strip "query_result()" and
        # get specific result.
        query = query[13:-1]
        result = [convert_to_human_readable_string(entity["metric"])
                  for entity in self.get_query(query)]
        if regex is not None:
            regex = regex.strip("/")
            result = [re.search(regex, item).group(1) for item in result]
        return result

    def do_query(self, query, regex=None, **kwargs):
        if "label_values" in query:
            return self._do_label_values_query(query)
        if "query_result" in query:
            return self._do_query_result_query(query, regex)
        return self.get_query(query, **kwargs)

    @staticmethod
    def compile_query(query, replaces):
        for pattern, value in replaces.items():
            query = query.replace(pattern, value)
        return query

    def get_all_measurements(self):
        if self.measurements is None:
            self.measurements = set(self.get_label_values("__name__"))
            self.measurements.discard("ALERTS")
        return self.measurements

    def parse_measurement(self, query):
        for measurement in self.get_all_measurements():
            if measurement in query:
                return measurement


def get_prometheus_client_from_config(config):
    api_client = PrometheusClient(
        "http://{0}:{1}/".format(
            config["prometheus_vip"],
            config["prometheus_server_port"])
    )
    return api_client
