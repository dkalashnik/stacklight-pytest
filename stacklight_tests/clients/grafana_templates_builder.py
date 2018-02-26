import collections
import itertools
import re

from stacklight_tests import utils


class TemplatesTree(object):
    def __init__(self, queries, datasource):
        self.queries = queries
        self.default_templates = {
            "$interval": "1m",
            "$timeFilter": "time > now() - 1h",
        }
        self.dependencies = {
            k: self.parse_dependencies(v) for k, (v, _) in self.queries.items()
        }
        self._compile_query = datasource.compile_query
        self._do_query = datasource.do_query

        self.nodes_by_level = collections.defaultdict(set)
        self.levels_by_name = collections.OrderedDict()
        self._build_abs_tree()

        if self.queries:
            self._build()

    @staticmethod
    def parse_dependencies(query):
        return re.findall("\$\w+", query)

    def _build_abs_tree(self):
        """Builds abstract tree of dependencies.

        For example it will build next tree for next dependencies:
            {'$environment': [],
             '$server': ['$environment'],
             '$peer': ['$environment', '$server'],
             '$volume': ['$environment', '$server']}

            $environment
                  |
                  v
               $server
                /  \
               v    v
            $peer  $volume
        """
        curr_level = 0
        for template, deps in utils.topo_sort(self.dependencies):
            if deps:
                curr_level = self.find_closest_parent_level(deps) + 1
            self.levels_by_name[template] = curr_level

    def _query_values_for_template(self, template, substitutions):
        query = self._compile_query(self.queries[template][0], substitutions)
        try:
            values = self._do_query(query, regex=self.queries[template][1])
        except KeyError:
            values = []
        return values

    def _fill_top_level(self):
        dep_name = self.levels_by_name.keys()[0]
        parent = None
        values = self._query_values_for_template(dep_name, {})
        for value in values:
            self.add_template(value, dep_name, parent)

    def _build(self):
        """Fill tree with all possible values for _templates_tree.

        For example:
                     mkX-lab-name.local
                    /        |        \
                   /         |         \
                  v          v          v
         ...<--ctl01       ctl02        ctl03-->...
                       /-----|--------\
                 /-----      |---\     ---------\
                v            |    ----\          v
           172.16.10.101     v         v     172.16.10.102
                          glance  keystone-keys

        """
        self._fill_top_level()
        for name, level in self.levels_by_name.items()[1:]:
            parents = self.get_closest_parents(self.dependencies[name])
            for parent in parents:
                substitutions = parent.get_full_template()
                values = self._query_values_for_template(name, substitutions)
                for value in values:
                    self.add_template(value, name, parent)

    def get_nodes_on_level(self, level):
        return self.nodes_by_level[level]

    def get_nodes_by_name(self, name):
        return (node for node in
                self.get_nodes_on_level(self.levels_by_name[name])
                if node.name == name)

    def find_closest_parent_level(self, dependencies):
        return max(self.levels_by_name[dep]
                   for dep in dependencies) if dependencies else 0

    def get_closest_parents(self, dependencies):
        parent_level = self.find_closest_parent_level(dependencies)
        return [node for node in self.get_nodes_on_level(parent_level)
                if node.name in dependencies]

    def add_template(self, value, name, parent):
        tpl = value
        if not isinstance(tpl, (str, unicode)):
            tpl = tpl[1]
        dependencies = self.dependencies[name]
        new_node = DepNode(tpl, name, parent, dependencies)
        self.nodes_by_level[new_node.level].add(new_node)

    def get_all_templates_for_query(self, query):
        dependencies = [dep for dep in self.parse_dependencies(query)
                        if dep not in self.default_templates]
        if not dependencies:
            return [self.default_templates]
        dep_nodes = self.get_closest_parents(dependencies)
        groups = {node.name for node in dep_nodes}
        if len(groups) > 1:
            parents = {node.parent for node in dep_nodes}
            templates = \
                list(itertools.chain(*[parent.get_templates_with_children()
                                       for parent in parents]))
        else:
            templates = [node.get_full_template() for node in dep_nodes]
        for template in templates:
            template.update(self.default_templates)
        return templates


class DepNode(object):
    def __init__(self, value, template_name, parent, dependencies=()):
        self.value = value
        self.name = template_name
        self.parent = parent
        self.children = set()
        self.level = getattr(parent, "level", -1) + 1
        self.dependencies = dependencies
        if parent is not None:
            self.parent.children.add(self)

    def __repr__(self):
        return "{}:{}:{}".format(
            self.__class__.__name__, self.name, self.value)

    def __str__(self):
        return self.value

    def get_full_template(self):
        curr_node = self
        template = {}
        while curr_node.parent:
            parent = curr_node.parent
            template[parent.name] = str(parent)
            curr_node = parent
        template[self.name] = self.value
        return template

    def get_templates_with_children(self):
        base_template = self.get_full_template()
        children_groups = collections.defaultdict(set)
        for child in self.children:
            children_groups[child.name].add(child.value)
        templates = []
        for item in itertools.product(*children_groups.values()):
            template = base_template.copy()
            for n, key in enumerate(children_groups.keys()):
                template[key] = item[n]
            templates.append(template)
        return templates
