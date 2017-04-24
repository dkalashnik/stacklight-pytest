import re

from stacklight_tests.clients import http_client


class PrometheusMetricClient(http_client.HttpClient):
    metric_line_regex = (r'(?P<metric_name>[\w\d_]+)'
                         r'({(?P<metric_meta>.*)})* '
                         r'(?P<metric_value>.*)')

    metric_meta_regex = r'(?P<meta_name>\w*)="(?P<meta_value>[\w\d\_\-]*)"'

    def parse_raw(self, lines):
        metrics = []

        for line in lines:
            if line[0] == "#":
                continue

            result = re.match(self.metric_line_regex, line)
            metric = {
                "name": result.group("metric_name"),
                "value": result.group("metric_value"),
                "meta": None,
            }

            meta = result.group("metric_meta")
            if meta is not None:
                metric["meta"] = dict(re.findall(self.metric_meta_regex, meta))

            metrics.append(metric)

        return metrics

    def get_metrics(self):
        _, resp = self.get("/metrics")

        return self.parse_raw(resp.splitlines())
