import re
from typing import Any, Iterable, Iterator, List, Match, Pattern, Union, cast
from w3lib.html import replace_entities as w3lib_replace_entities


def flatten(x: Iterable[Any]) ->List[Any]:
    """flatten(sequence) -> list
    Returns a single, flat list which contains all elements retrieved
    from the sequence and all recursively contained sub-sequences
    (iterables).
    Examples:
    >>> [1, 2, [3,4], (5,6)]
    [1, 2, [3, 4], (5, 6)]
    >>> flatten([[[1,2,3], (42,None)], [4,5], [6], 7, (8,9,10)])
    [1, 2, 3, 42, None, 4, 5, 6, 7, 8, 9, 10]
    >>> flatten(["foo", "bar"])
    ['foo', 'bar']
    >>> flatten(["foo", ["baz", 42], "bar"])
    ['foo', 'baz', 42, 'bar']
    """
    result = []
    for el in x:
        if _is_listlike(el):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result


def iflatten(x: Iterable[Any]) ->Iterator[Any]:
    """iflatten(sequence) -> Iterator
    Similar to ``.flatten()``, but returns iterator instead"""
    for el in x:
        if _is_listlike(el):
            yield from iflatten(el)
        else:
            yield el


def _is_listlike(x: Any) ->bool:
    """
    >>> _is_listlike("foo")
    False
    >>> _is_listlike(5)
    False
    >>> _is_listlike(b"foo")
    False
    >>> _is_listlike([b"foo"])
    True
    >>> _is_listlike((b"foo",))
    True
    >>> _is_listlike({})
    True
    >>> _is_listlike(set())
    True
    >>> _is_listlike((x for x in range(3)))
    True
    >>> _is_listlike(range(5))
    True
    """
    return (
        hasattr(x, '__iter__') and
        not isinstance(x, (str, bytes))
    )


def extract_regex(regex: Union[str, Pattern[str]], text: str,
    replace_entities: bool=True) ->List[str]:
    """Extract a list of strings from the given text/encoding using the following policies:
    * if the regex contains a named group called "extract" that will be returned
    * if the regex contains multiple numbered groups, all those will be returned (flattened)
    * if the regex doesn't contain any group the entire regex matching is returned
    """
    if isinstance(regex, str):
        regex = re.compile(regex)

    if replace_entities:
        text = w3lib_replace_entities(text)

    if 'extract' in regex.groupindex:
        extracted = [match.group('extract') for match in regex.finditer(text)]
    elif regex.groups > 0:
        extracted = [cast(Match[str], match).groups() for match in regex.finditer(text)]
        extracted = flatten(extracted)
    else:
        extracted = regex.findall(text)

    return [str(s) for s in extracted]


def shorten(text: str, width: int, suffix: str='...') ->str:
    """Truncate the given text to fit in the given width."""
    if len(text) <= width:
        return text
    return text[:width - len(suffix)] + suffix
