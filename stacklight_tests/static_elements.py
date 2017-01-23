import cssselect
from lxml import html

from stacklight_tests.custom_exceptions import NotFound


class By(object):
    """
    Set of supported locator strategies.
    """

    ID = "id"
    XPATH = "xpath"
    NAME = "name"
    TAG_NAME = "tag name"
    CLASS_NAME = "class name"
    CSS_SELECTOR = "css selector"

    translator = cssselect.GenericTranslator()

    @classmethod
    def convert_selector_to_xpath(cls, by=ID, value=None):
        if by == cls.ID:
            by = cls.CSS_SELECTOR
            value = '[id="%s"]' % value
        elif by == cls.TAG_NAME:
            by = cls.CSS_SELECTOR
        elif by == cls.CLASS_NAME:
            by = cls.CSS_SELECTOR
            value = ".%s" % value
        elif by == cls.NAME:
            by = cls.CSS_SELECTOR
            value = '[name="%s"]' % value
        if by == cls.CSS_SELECTOR:
            value = cls.translator.css_to_xpath(value)
        return value


class BaseElement(object):
    element = None
    tag = None

    def __init__(self, source=None, element=None):
        """Base class for every element
        :param source: html source code
        :type source: binary string
        :param element: element
        :type element: lxml.Element
        """
        if (not source) and (element is None):
            raise ValueError(
                "Html source or LXML Element object should be provided")
        if source:
            if element:
                raise ValueError(
                    "Only one initialization option should be provided")
            self.element = html.fromstring(source)
        if element is not None:
            self.element = element

    def __getattr__(self, item):
        return getattr(self.element, item)

    @staticmethod
    def _determine(element):
        return ElementDeterminator.determine(element)

    @property
    def full_text(self):
        return self.element.text_content()

    @property
    def text_(self):
        return self.full_text.strip()

    @property
    def html(self):
        return html.tostring(self.element)

    @property
    def parent(self):
        parent_element = self.getparent()
        return self._determine(parent_element) if parent_element else None

    @property
    def children(self):
        return [self._determine(element) for element in self.getchildren()]

    def find_element_by_id(self, id_):
        """Finds element within this element's children by ID.

        :Args:
            - id_ - ID of child element to locate.
        """
        return self.find_element(by=By.ID, value=id_)

    def find_elements_by_id(self, id_):
        """Finds a list of elements within this element's children by ID.

        :Args:
            - id_ - Id of child element to find.
        """
        return self.find_elements(by=By.ID, value=id_)

    def find_element_by_name(self, name):
        """Finds element within this element's children by name.

        :Args:
            - name - name property of the element to find.
        """
        return self.find_element(by=By.NAME, value=name)

    def find_elements_by_name(self, name):
        """Finds a list of elements within this element's children by name.

        :Args:
            - name - name property to search for.
        """
        return self.find_elements(by=By.NAME, value=name)

    def find_element_by_tag_name(self, name):
        """Finds element within this element's children by tag name.

        :Args:
            - name - name of html tag (eg: h1, a, span)
        """
        return self.find_element(by=By.TAG_NAME, value=name)

    def find_elements_by_tag_name(self, name):
        """Finds a list of elements within this element's children by tag name.

        :Args:
            - name - name of html tag (eg: h1, a, span)
        """
        return self.find_elements(by=By.TAG_NAME, value=name)

    def find_element_by_xpath(self, xpath):
        """Finds element by xpath.

        :Args:
            xpath - xpath of element to locate.  "//input[@class='myelement']"

        Note: The base path will be relative to this element's location.

        This will select the first link under this element.

        ::

            myelement.find_elements_by_xpath(".//a")

        However, this will select the first link on the page.

        ::

            myelement.find_elements_by_xpath("//a")

        """
        return self.find_element(by=By.XPATH, value=xpath)

    def find_elements_by_xpath(self, xpath):
        """Finds elements within the element by xpath.

        :Args:
            - xpath - xpath locator string.

        Note: The base path will be relative to this element's location.

        This will select all links under this element.

        ::

            myelement.find_elements_by_xpath(".//a")

        However, this will select all links in the page itself.

        ::

            myelement.find_elements_by_xpath("//a")

        """
        return self.find_elements(by=By.XPATH, value=xpath)

    def find_element_by_class_name(self, name):
        """Finds element within this element's children by class name.

        :Args:
            - name - class name to search for.
        """
        return self.find_element(by=By.CLASS_NAME, value=name)

    def find_elements_by_class_name(self, name):
        """Finds a list of elements within this element's children by class name.

        :Args:
            - name - class name to search for.
        """
        return self.find_elements(by=By.CLASS_NAME, value=name)

    def find_element_by_css_selector(self, css_selector):
        """Finds element within this element's children by CSS selector.

        :Args:
            - css_selector - CSS selctor string, ex: 'a.nav#home'
        """
        return self.find_element(by=By.CSS_SELECTOR, value=css_selector)

    def find_elements_by_css_selector(self, css_selector):
        """Finds a list of elements within this element's children by CSS selector.

        :Args:
            - css_selector - CSS selctor string, ex: 'a.nav#home'
        """
        return self.find_elements(by=By.CSS_SELECTOR, value=css_selector)

    def find_elements(self, by=By.XPATH, value=None):
        value = By.convert_selector_to_xpath(by, value)
        elements = self.element.xpath(value)
        if not elements:
            raise NotFound(
                "No elements found by selector: {} and value: {} "
                "in element: {}".format(by, value, self.html)
            )
        return [self._determine(element) for element in elements]

    def find_element(self, by=By.XPATH, value=None):
        return self.find_elements(by, value)[0]


class Page(BaseElement):
    tag = "html"
    title_locator = (By.XPATH, "//title")

    @property
    def title(self):
        return self.find_element(*self.title_locator).full_text


class Table(BaseElement):
    tag = "table"

    def get_size(self):
        length = len(self)
        width = max(
            (len(row.find_elements_by_xpath("th|td")) for row in self.rows))
        return length, width

    @property
    def size(self):
        return self.get_size()

    def __len__(self):
        return len(self.find_elements_by_xpath("tr[position() > 0]"))

    def get_row(self, row_id):
        return self.find_element_by_xpath("tr[{0}]".format(row_id))

    def get_cell(self, row_id, column_id):
        row = self.get_row(row_id)
        return row.get_cell(column_id)

    @property
    def rows(self):
        return [self.get_row(row_id) for row_id in range(1, len(self) + 1)]

    @property
    def cells(self):
        return [row.cells for row in self.rows]


class TableRow(BaseElement):
    tag = "tr"

    def __len__(self):
        return

    def get_cell(self, column_id):
        try:
            return self.find_element_by_xpath("td[{0}]".format(column_id))
        except NotFound:
            # Trying to return header cells, if row don't contain common cells
            return self.find_element_by_xpath("th[{0}]".format(column_id))

    @property
    def cells(self):
        try:
            return self.find_elements_by_xpath("td")
        except NotFound:
            return []


class ElementDeterminator(object):
    tag_mapping = None

    @classmethod
    def mapping(cls):
        if cls.tag_mapping is None:
            cls.tag_mapping = {value.tag: value
                               for value in globals().values()
                               if issubclass(type(value), type) and
                               issubclass(value, BaseElement)}
        return cls.tag_mapping

    @classmethod
    def determine(cls, element):
        tag_mapping = cls.mapping()
        element_cls = tag_mapping.get(element.tag, tag_mapping[None])
        return element_cls(element=element)
