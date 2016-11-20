import elasticsearch


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
