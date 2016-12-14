import logging

import elasticsearch

from stacklight_tests import utils

logger = logging.getLogger(__name__)


class EsKibanaApi(object):
    def __init__(self, host, port=9200):
        super(EsKibanaApi, self).__init__()
        self.es = elasticsearch.Elasticsearch(
            [{'host': host, 'port': port}])
        self._kibana_protocol = None

    def query_elasticsearch(self, index_type, time_range="now-1h",
                            query_filter="*", size=100):
        all_indices = self.es.indices.get_aliases().keys()
        indices = filter(lambda x: index_type in x, sorted(all_indices))
        return self.es.search(
            index=indices,
            body={
                "query": {"filtered": {
                    "query": {"bool": {"should": {"query_string": {
                        "query": query_filter}}}},
                    "filter": {"bool": {"must": {"range": {
                        "Timestamp": {"from": time_range}}}}}}},
                "size": size})

    def check_notifications(self, expected_notifications, timeout=5 * 60,
                            interval=10, **kwargs):
        def _verify_notifications(expected_list):
            output = self.query_elasticsearch(**kwargs)
            got_list = list(
                set([hit["_source"]["event_type"]
                     for hit in output["hits"]["hits"]]))
            for event_type in expected_list:
                if event_type not in got_list:
                    logger.info("{} event type not found in {}".format(
                        event_type, got_list))
                    return False
            return True

        logger.info("Waiting to get all notifications")
        msg = "Timed out waiting to get all notifications"
        utils.wait(
            lambda: _verify_notifications(expected_notifications),
            timeout=timeout, interval=interval, timeout_msg=msg)
