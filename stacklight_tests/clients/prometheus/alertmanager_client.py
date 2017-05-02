import json
import logging

from stacklight_tests.clients import http_client
from stacklight_tests.clients.prometheus import prometheus_client
from stacklight_tests import utils


logger = logging.getLogger(__name__)


class AlertBehaviorMixin(object):
    def get_alert_by_filter(self, **criteria):
        alerts = [alert for alert in self.list_alerts()
                  if alert.is_appropriate(**criteria)]
        if alerts:
            return alerts[0]
        return None

    def get_alert_status(self, criteria):
        alert = self.get_alert_by_filter(**criteria)
        if not alert:
            logger.debug("Alert is not found.")
            return False
        return alert.is_fired

    def check_alert_status(self, criteria, is_fired=True, timeout=5 * 60):
        def check():
            logger.debug("Awaiting alert {} is{} fired.".format(
                criteria, " not" if not is_fired else ""))
            status = self.get_alert_status(criteria)
            logger.debug("Alert is{} fired.".format(
                " not" if not status else ""))
            return status == is_fired
        msg = "Alert status was not changed."
        return utils.wait(check, timeout=timeout, timeout_msg=msg)


class AlertManagerClient(AlertBehaviorMixin, http_client.HttpClient):
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
        return [get_alert_from_alert_manager_dict(item)
                for item in status["data"]]

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


class PrometheusQueryAlertClient(AlertBehaviorMixin,
                                 prometheus_client.PrometheusClient):
    @staticmethod
    def _remove_pending_alerts(data):
        """Clean from pending alerts."""
        data = [item for item in data
                if item["metric"]["alertstate"] == "firing"]
        return data

    @staticmethod
    def _merge_duplicates(alerts):
        """Merge same alerts into one.

        Prometheus query api can return the same objects repeatedly, so
        it is needed to get rid of duplicates

        :raises: ValueError in case of two alerts are equal with different time
         or if in the same time we have different values.
        """
        uniqual_alerts = {}
        for alert in alerts:
            if alert not in uniqual_alerts:
                uniqual_alerts[alert] = alert
            elif uniqual_alerts[alert].time != alert.time:
                raise ValueError("Unresolved merge situation.")
            elif uniqual_alerts[alert].value != alert.value:
                uniqual_alerts[alert].value = (
                    (uniqual_alerts[alert].value + alert.value) / 2)
        return uniqual_alerts.values()

    def list_alerts(self):
        data = self.get_query("ALERTS")
        data = self._remove_pending_alerts(data)
        alerts = [get_alert_from_query_dict(item) for item in data]
        alerts = self._merge_duplicates(alerts)
        return alerts


class Alert(object):
    def __init__(self, name, time, host, service, severity,
                 value=None, annotations=None):
        self.name = name
        self.time = time
        self.host = host
        self.service = service
        self.severity = severity
        self.value = value
        self.annotations = annotations

    def is_appropriate(self, **criteria):
        for attr, value in criteria.items():
            if not getattr(self, attr) == value:
                return False
        return True


class AlertManagerAlert(Alert):
    started_at = None
    ended_at = None

    @property
    def is_fired(self):
        if self.started_at is None:
            started_at, ended_at = self.time
            self.started_at = utils.parse_time_rfc_3339(started_at)
            self.ended_at = utils.parse_time_rfc_3339(ended_at)
        return self.ended_at < self.started_at


class PrometheusQueryAlert(Alert):
    valuable_attrs = ("name", "host", "service")

    def __hash__(self):
        unique_string = "".join(getattr(self, attr)
                                for attr in self.valuable_attrs)
        return hash(unique_string)

    def __eq__(self, other):
        for attr in self.valuable_attrs:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True

    def __ne__(self, other):
        return not self == other

    @property
    def is_fired(self):
        return self.value


def get_alert_from_alert_manager_dict(json_repr):
    return AlertManagerAlert(
        name=json_repr["labels"]["alertname"],
        time=(json_repr["startsAt"], json_repr["endsAt"]),
        host=json_repr["labels"]["host"],
        service=json_repr["labels"]["service"],
        severity=json_repr["labels"]["severity"],
        annotations=json_repr["annotations"],
    )


def get_alert_from_query_dict(json_repr):
    return PrometheusQueryAlert(
        name=json_repr["metric"]["alertname"],
        time=json_repr["value"][0],
        host=json_repr["metric"].get("host", ""),
        service=json_repr["metric"]["service"],
        severity=json_repr["metric"]["severity"],
        value=int(json_repr["value"][1]),
    )
