"""XPath and JMESPath selectors based on the lxml and jmespath Python
packages."""
import json
import typing
import warnings
from io import BytesIO
from typing import Any, Dict, List, Literal, Mapping, Optional, Pattern, SupportsIndex, Tuple, Type, TypedDict, TypeVar, Union
from warnings import warn
import jmespath
from lxml import etree, html
from packaging.version import Version
from .csstranslator import GenericTranslator, HTMLTranslator
from .utils import extract_regex, flatten, iflatten, shorten
_SelectorType = TypeVar('_SelectorType', bound='Selector')
_ParserType = Union[etree.XMLParser, etree.HTMLParser]
_TostringMethodType = Literal['html', 'xml']
lxml_version = Version(etree.__version__)
lxml_huge_tree_version = Version('4.2')
LXML_SUPPORTS_HUGE_TREE = lxml_version >= lxml_huge_tree_version


class CannotRemoveElementWithoutRoot(Exception):
    pass


class CannotRemoveElementWithoutParent(Exception):
    pass


class CannotDropElementWithoutParent(CannotRemoveElementWithoutParent):
    pass


class SafeXMLParser(etree.XMLParser):

    def __init__(self, *args: Any, **kwargs: Any) ->None:
        kwargs.setdefault('resolve_entities', False)
        super().__init__(*args, **kwargs)


class CTGroupValue(TypedDict):
    _parser: Union[Type[etree.XMLParser], Type[html.HTMLParser]]
    _csstranslator: Union[GenericTranslator, HTMLTranslator]
    _tostring_method: str


_ctgroup: Dict[str, CTGroupValue] = {'html': {'_parser': html.HTMLParser,
    '_csstranslator': HTMLTranslator(), '_tostring_method': 'html'}, 'xml':
    {'_parser': SafeXMLParser, '_csstranslator': GenericTranslator(),
    '_tostring_method': 'xml'}}


def create_root_node(text: str, parser_cls: Type[_ParserType], base_url:
    Optional[str]=None, huge_tree: bool=LXML_SUPPORTS_HUGE_TREE, body:
    bytes=b'', encoding: str='utf8') ->etree._Element:
    """Create root node for text using given parser class."""
    parser = parser_cls(recover=True, encoding=encoding)
    if LXML_SUPPORTS_HUGE_TREE:
        parser.set_option(etree.XML_PARSE_HUGE, huge_tree)
    if body:
        text = body.decode(encoding)
    root = etree.fromstring(text.encode('utf-8'), parser=parser, base_url=base_url)
    if root is None:
        root = etree.fromstring('<html/>', parser=parser, base_url=base_url)
    return root


class SelectorList(List[_SelectorType]):
    """
    The :class:`SelectorList` class is a subclass of the builtin ``list``
    class, which provides a few additional methods.
    """

    @typing.overload
    def __getitem__(self, pos: 'SupportsIndex') ->_SelectorType:
        pass

    @typing.overload
    def __getitem__(self, pos: slice) ->'SelectorList[_SelectorType]':
        pass

    def __getitem__(self, pos: Union['SupportsIndex', slice]) ->Union[
        _SelectorType, 'SelectorList[_SelectorType]']:
        o = super().__getitem__(pos)
        if isinstance(pos, slice):
            return self.__class__(typing.cast('SelectorList[_SelectorType]', o)
                )
        else:
            return typing.cast(_SelectorType, o)

    def __getstate__(self) ->None:
        raise TypeError("can't pickle SelectorList objects")

    def jmespath(self, query: str, **kwargs: Any
        ) ->'SelectorList[_SelectorType]':
        """
        Call the ``.jmespath()`` method for each element in this list and return
        their results flattened as another :class:`SelectorList`.

        ``query`` is the same argument as the one in :meth:`Selector.jmespath`.

        Any additional named arguments are passed to the underlying
        ``jmespath.search`` call, e.g.::

            selector.jmespath('author.name', options=jmespath.Options(dict_cls=collections.OrderedDict))
        """
        return self.__class__(flatten([x.jmespath(query, **kwargs) for x in self]))

    def xpath(self, xpath: str, namespaces: Optional[Mapping[str, str]]=
        None, **kwargs: Any) ->'SelectorList[_SelectorType]':
        """
        Call the ``.xpath()`` method for each element in this list and return
        their results flattened as another :class:`SelectorList`.

        ``xpath`` is the same argument as the one in :meth:`Selector.xpath`

        ``namespaces`` is an optional ``prefix: namespace-uri`` mapping (dict)
        for additional prefixes to those registered with ``register_namespace(prefix, uri)``.
        Contrary to ``register_namespace()``, these prefixes are not
        saved for future calls.

        Any additional named arguments can be used to pass values for XPath
        variables in the XPath expression, e.g.::

            selector.xpath('//a[href=$url]', url="http://www.example.com")
        """
        return self.__class__(flatten([x.xpath(xpath, namespaces=namespaces, **kwargs) for x in self]))

    def css(self, query: str) ->'SelectorList[_SelectorType]':
        """
        Call the ``.css()`` method for each element in this list and return
        their results flattened as another :class:`SelectorList`.

        ``query`` is the same argument as the one in :meth:`Selector.css`
        """
        return self.__class__(flatten([x.css(query) for x in self]))

    def re(self, regex: Union[str, Pattern[str]], replace_entities: bool=True
        ) ->List[str]:
        """
        Call the ``.re()`` method for each element in this list and return
        their results flattened, as a list of strings.

        By default, character entity references are replaced by their
        corresponding character (except for ``&amp;`` and ``&lt;``.
        Passing ``replace_entities`` as ``False`` switches off these
        replacements.
        """
        return flatten([x.re(regex, replace_entities=replace_entities) for x in self])

    def re_first(self, regex: Union[str, Pattern[str]], default: Optional[
        str]=None, replace_entities: bool=True) ->Optional[str]:
        """
        Call the ``.re()`` method for the first element in this list and
        return the result in an string. If the list is empty or the
        regex doesn't match anything, return the default value (``None`` if
        the argument is not provided).

        By default, character entity references are replaced by their
        corresponding character (except for ``&amp;`` and ``&lt;``.
        Passing ``replace_entities`` as ``False`` switches off these
        replacements.
        """
        for el in iflatten(self):
            m = el.re(regex, replace_entities=replace_entities)
            if m:
                return m[0]
        return default

    def getall(self) ->List[str]:
        """
        Call the ``.get()`` method for each element is this list and return
        their results flattened, as a list of strings.
        """
        return [x.get() for x in self]
    extract = getall

    def get(self, default: Optional[str]=None) ->Any:
        """
        Return the result of ``.get()`` for the first element in this list.
        If the list is empty, return the default value.
        """
        for x in self:
            return x.get()
        return default
    extract_first = get

    @property
    def attrib(self) ->Mapping[str, str]:
        """Return the attributes dictionary for the first element.
        If the list is empty, return an empty dict.
        """
        for x in self:
            return x.attrib
        return {}

    def remove(self) ->None:
        """
        Remove matched nodes from the parent for each element in this list.
        """
        for x in self:
            x.remove()

    def drop(self) ->None:
        """
        Drop matched nodes from the parent for each element in this list.
        """
        for x in self:
            x.drop()


_NOT_SET = object()


class Selector:
    """Wrapper for input data in HTML, JSON, or XML format, that allows
    selecting parts of it using selection expressions.

    You can write selection expressions in CSS or XPath for HTML and XML
    inputs, or in JMESPath for JSON inputs.

    ``text`` is an ``str`` object.

    ``body`` is a ``bytes`` object. It can be used together with the
    ``encoding`` argument instead of the ``text`` argument.

    ``type`` defines the selector type. It can be ``"html"`` (default),
    ``"json"``, or ``"xml"``.

    ``base_url`` allows setting a URL for the document. This is needed when looking up external entities with relative paths.
    See the documentation for :func:`lxml.etree.fromstring` for more information.

    ``huge_tree`` controls the lxml/libxml2 feature that forbids parsing
    certain large documents to protect from possible memory exhaustion. The
    argument is ``True`` by default if the installed lxml version supports it,
    which disables the protection to allow parsing such documents. Set it to
    ``False`` if you want to enable the protection.
    See `this lxml FAQ entry <https://lxml.de/FAQ.html#is-lxml-vulnerable-to-xml-bombs>`_
    for more information.
    """
    __slots__ = ['namespaces', 'type', '_expr', '_huge_tree', 'root',
        '_text', 'body', '__weakref__']
    _default_namespaces = {'re': 'http://exslt.org/regular-expressions',
        'set': 'http://exslt.org/sets'}
    _lxml_smart_strings = False
    selectorlist_cls = SelectorList['Selector']

    def __init__(self, text: Optional[str]=None, type: Optional[str]=None,
        body: bytes=b'', encoding: str='utf8', namespaces: Optional[Mapping
        [str, str]]=None, root: Optional[Any]=_NOT_SET, base_url: Optional[
        str]=None, _expr: Optional[str]=None, huge_tree: bool=
        LXML_SUPPORTS_HUGE_TREE) ->None:
        self.root: Any
        if type not in ('html', 'json', 'text', 'xml', None):
            raise ValueError(f'Invalid type: {type}')
        if text is None and not body and root is _NOT_SET:
            raise ValueError('Selector needs text, body, or root arguments')
        if text is not None and not isinstance(text, str):
            msg = f'text argument should be of type str, got {text.__class__}'
            raise TypeError(msg)
        if text is not None:
            if root is not _NOT_SET:
                warnings.warn(
                    'Selector got both text and root, root is being ignored.',
                    stacklevel=2)
            if not isinstance(text, str):
                msg = (
                    f'text argument should be of type str, got {text.__class__}'
                    )
                raise TypeError(msg)
            root, type = _get_root_and_type_from_text(text, input_type=type,
                base_url=base_url, huge_tree=huge_tree)
            self.root = root
            self.type = type
        elif body:
            if not isinstance(body, bytes):
                msg = (
                    f'body argument should be of type bytes, got {body.__class__}'
                    )
                raise TypeError(msg)
            root, type = _get_root_and_type_from_bytes(body=body, encoding=
                encoding, input_type=type, base_url=base_url, huge_tree=
                huge_tree)
            self.root = root
            self.type = type
        elif root is _NOT_SET:
            raise ValueError('Selector needs text, body, or root arguments')
        else:
            self.root = root
            self.type = _get_root_type(root, input_type=type)
        self.namespaces = dict(self._default_namespaces)
        if namespaces is not None:
            self.namespaces.update(namespaces)
        self._expr = _expr
        self._huge_tree = huge_tree
        self._text = text

    def __getstate__(self) ->Any:
        raise TypeError("can't pickle Selector objects")

    def jmespath(self: _SelectorType, query: str, **kwargs: Any
        ) ->SelectorList[_SelectorType]:
        """
        Find objects matching the JMESPath ``query`` and return the result as a
        :class:`SelectorList` instance with all elements flattened. List
        elements implement :class:`Selector` interface too.

        ``query`` is a string containing the `JMESPath
        <https://jmespath.org/>`_ query to apply.

        Any additional named arguments are passed to the underlying
        ``jmespath.search`` call, e.g.::

            selector.jmespath('author.name', options=jmespath.Options(dict_cls=collections.OrderedDict))
        """
        result = jmespath.search(query, self.get(), **kwargs)
        if isinstance(result, list):
            return self.selectorlist_cls(Selector(root=r, _expr=query) for r in result)
        else:
            return self.selectorlist_cls([Selector(root=result, _expr=query)])

    def xpath(self: _SelectorType, query: str, namespaces: Optional[Mapping
        [str, str]]=None, **kwargs: Any) ->SelectorList[_SelectorType]:
        """
        Find nodes matching the xpath ``query`` and return the result as a
        :class:`SelectorList` instance with all elements flattened. List
        elements implement :class:`Selector` interface too.

        ``query`` is a string containing the XPATH query to apply.

        ``namespaces`` is an optional ``prefix: namespace-uri`` mapping (dict)
        for additional prefixes to those registered with ``register_namespace(prefix, uri)``.
        Contrary to ``register_namespace()``, these prefixes are not
        saved for future calls.

        Any additional named arguments can be used to pass values for XPath
        variables in the XPath expression, e.g.::

            selector.xpath('//a[href=$url]', url="http://www.example.com")
        """
        try:
            xpathev = self.root.xpath
        except AttributeError:
            return self.selectorlist_cls([])

        nsp = dict(self.namespaces)
        if namespaces is not None:
            nsp.update(namespaces)
        try:
            result = xpathev(query, namespaces=nsp, smart_strings=self._lxml_smart_strings, **kwargs)
        except etree.XPathError as exc:
            msg = f"XPath error: {exc} in {query}"
            raise ValueError(msg)

        if type(result) is not list:
            result = [result]

        return self.selectorlist_cls(self.__class__(root=x, _expr=query)
                                     for x in result)

    def css(self: _SelectorType, query: str) ->SelectorList[_SelectorType]:
        """
        Apply the given CSS selector and return a :class:`SelectorList` instance.

        ``query`` is a string containing the CSS selector to apply.

        In the background, CSS queries are translated into XPath queries using
        `cssselect`_ library and run ``.xpath()`` method.

        .. _cssselect: https://pypi.python.org/pypi/cssselect/
        """
        return self.xpath(_ctgroup[self.type]['_csstranslator'].css_to_xpath(query))

    def re(self, regex: Union[str, Pattern[str]], replace_entities: bool=True
        ) ->List[str]:
        """
        Apply the given regex and return a list of strings with the
        matches.

        ``regex`` can be either a compiled regular expression or a string which
        will be compiled to a regular expression using ``re.compile(regex)``.

        By default, character entity references are replaced by their
        corresponding character (except for ``&amp;`` and ``&lt;``).
        Passing ``replace_entities`` as ``False`` switches off these
        replacements.
        """
        return extract_regex(regex, self.get(), replace_entities=replace_entities)

    def re_first(self, regex: Union[str, Pattern[str]], default: Optional[
        str]=None, replace_entities: bool=True) ->Optional[str]:
        """
        Apply the given regex and return the first string which matches. If
        there is no match, return the default value (``None`` if the argument
        is not provided).

        By default, character entity references are replaced by their
        corresponding character (except for ``&amp;`` and ``&lt;``).
        Passing ``replace_entities`` as ``False`` switches off these
        replacements.
        """
        return next(iflatten(self.re(regex, replace_entities)), default)

    def get(self) ->Any:
        """
        Serialize and return the matched nodes.

        For HTML and XML, the result is always a string, and percent-encoded
        content is unquoted.
        """
        try:
            return etree.tostring(self.root,
                                  method=_ctgroup[self.type]['_tostring_method'],
                                  encoding='unicode',
                                  with_tail=False)
        except (AttributeError, TypeError):
            if self.root is True:
                return '1'
            elif self.root is False:
                return '0'
            else:
                return str(self.root)
    extract = get

    def getall(self) ->List[str]:
        """
        Serialize and return the matched node in a 1-element list of strings.
        """
        return [self.get()]

    def register_namespace(self, prefix: str, uri: str) ->None:
        """
        Register the given namespace to be used in this :class:`Selector`.
        Without registering namespaces you can't select or extract data from
        non-standard namespaces. See :ref:`selector-examples-xml`.
        """
        self.namespaces[prefix] = uri

    def remove_namespaces(self) ->None:
        """
        Remove all namespaces, allowing to traverse the document using
        namespace-less xpaths. See :ref:`removing-namespaces`.
        """
        for el in self.root.iter('*'):
            if el.tag.startswith('{'):
                el.tag = el.tag.split('}', 1)[1]
            for an in list(el.attrib.keys()):
                if an.startswith('{'):
                    el.attrib[an.split('}', 1)[1]] = el.attrib.pop(an)

    def remove(self) ->None:
        """
        Remove matched nodes from the parent element.
        """
        parent = self.root.getparent()
        if parent is None:
            raise CannotRemoveElementWithoutRoot("Element has no parent")
        parent.remove(self.root)

    def drop(self) ->None:
        """
        Drop matched nodes from the parent element.
        """
        parent = self.root.getparent()
        if parent is None:
            raise CannotDropElementWithoutParent("Element has no parent")
        parent.drop(self.root)

    @property
    def attrib(self) ->Dict[str, str]:
        """Return the attributes dictionary for underlying element."""
        pass

    def __bool__(self) ->bool:
        """
        Return ``True`` if there is any real content selected or ``False``
        otherwise.  In other words, the boolean value of a :class:`Selector` is
        given by the contents it selects.
        """
        return bool(self.get())
    __nonzero__ = __bool__

    def __str__(self) ->str:
        return str(self.get())

    def __repr__(self) ->str:
        data = repr(shorten(str(self.get()), width=40))
        return f'<{type(self).__name__} query={self._expr!r} data={data}>'
