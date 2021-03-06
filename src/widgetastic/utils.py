# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""This module contains some supporting classes."""

import re
import string
from cached_property import cached_property
from smartloc import Locator
from threading import Lock

from . import xpath


class Widgetable(object):
    """A base class that should be a base class of anything that can be or act like a Widget."""
    #: Sequential counter that gets incremented on each Widgetable creation
    _seq_cnt = 0
    #: Lock that makes the :py:attr:`_seq_cnt` increment thread safe
    _seq_cnt_lock = Lock()

    def __new__(cls, *args, **kwargs):
        o = super(Widgetable, cls).__new__(cls)
        with Widgetable._seq_cnt_lock:
            o._seq_id = Widgetable._seq_cnt
            Widgetable._seq_cnt += 1
        return o

    @property
    def child_items(self):
        return []


class Version(object):
    """Version class based on :py:class:`distutils.version.LooseVersion`

    Has improved handling of the suffixes and such things.
    """
    #: List of possible suffixes
    SUFFIXES = ('nightly', 'pre', 'alpha', 'beta', 'rc')
    #: An autogenereted regexp from the :py:attr:`SUFFIXES`
    SUFFIXES_STR = "|".join(r'-{}(?:\d+(?:\.\d+)?)?'.format(suff) for suff in SUFFIXES)
    #: Regular expression that parses the main components of the version (not suffixes)
    component_re = re.compile(r'(?:\s*(\d+|[a-z]+|\.|(?:{})+$))'.format(SUFFIXES_STR))
    suffix_item_re = re.compile(r'^([^0-9]+)(\d+(?:\.\d+)?)?$')

    def __init__(self, vstring):
        self.parse(vstring)

    def __hash__(self):
        return hash(self.vstring)

    def parse(self, vstring):
        if vstring is None:
            raise ValueError('Version string cannot be None')
        elif isinstance(vstring, (list, tuple)):
            vstring = ".".join(map(str, vstring))
        elif vstring:
            vstring = str(vstring).strip()
        if vstring in ('master', 'latest', 'upstream'):
            vstring = 'master'

        components = list(filter(lambda x: x and x != '.', self.component_re.findall(vstring)))
        # Check if we have a version suffix which denotes pre-release
        if components and components[-1].startswith('-'):
            self.suffix = components[-1][1:].split('-')    # Chop off the -
            components = components[:-1]
        else:
            self.suffix = None
        for i in range(len(components)):
            try:
                components[i] = int(components[i])
            except ValueError:
                pass

        self.vstring = vstring
        self.version = components

    @cached_property
    def normalized_suffix(self):
        """Turns the string suffixes to numbers. Creates a list of tuples.

        The list of tuples is consisting of 2-tuples, the first value says the position of the
        suffix in the list and the second number the numeric value of an eventual numeric suffix.

        If the numeric suffix is not present in a field, then the value is 0
        """
        numberized = []
        if self.suffix is None:
            return numberized
        for item in self.suffix:
            suff_t, suff_ver = self.suffix_item_re.match(item).groups()
            if suff_ver is None or len(suff_ver) == 0:
                suff_ver = 0.0
            else:
                suff_ver = float(suff_ver)
            suff_t = self.SUFFIXES.index(suff_t)
            numberized.append((suff_t, suff_ver))
        return numberized

    @classmethod
    def latest(cls):
        """Returns a specific ``latest`` version which always evaluates as newer."""
        try:
            return cls._latest
        except AttributeError:
            cls._latest = cls('latest')
            return cls._latest

    @classmethod
    def lowest(cls):
        """Returns a specific ``lowest`` version which always evaluates as older.

        You shall use this value in your :py:class:`VersionPick` dictionaries to match the oldest
        possible version of the product.
        """
        try:
            return cls._lowest
        except AttributeError:
            cls._lowest = cls('lowest')
            return cls._lowest

    def __str__(self):
        return self.vstring

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, repr(self.vstring))

    def __lt__(self, other):
        try:
            if not isinstance(other, Version):
                other = Version(other)
        except:
            raise ValueError('Cannot compare Version to {}'.format(type(other).__name__))

        if self == other:
            return False
        elif self == self.latest() or other == self.lowest():
            return False
        elif self == self.lowest() or other == self.latest():
            return True
        else:
            # Start deciding on versions
            if self.version < other.version:
                return True
            # Use suffixes to decide
            elif self.suffix is None and other.suffix is None:
                # No suffix, the same
                return False
            elif self.suffix is None:
                # This does not have suffix but the other does so this is "newer"
                return False
            elif other.suffix is None:
                # This one does have suffix and the other does not so this one is older
                return True
            else:
                # Both have suffixes, so do some math
                return self.normalized_suffix < other.normalized_suffix

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        try:
            if not isinstance(other, type(self)):
                other = Version(other)
            return (
                self.version == other.version and self.normalized_suffix == other.normalized_suffix)
        except:
            return False

    def __contains__(self, ver):
        """Enables to use ``in`` expression for :py:meth:`Version.is_in_series`.

        Example:
            ``"5.5.5.2" in Version("5.5") returns ``True``

        Args:
            ver: Version that should be checked if it is in series of this version. If
                :py:class:`str` provided, it will be converted to :py:class:`Version`.
        """
        try:
            return Version(ver).is_in_series(self)
        except:
            return False

    def is_in_series(self, series):
        """This method checks whether the version belongs to another version's series.

        Eg.: ``Version("5.5.5.2").is_in_series("5.5")`` returns ``True``

        Args:
            series: Another :py:class:`Version` to check against. If string provided, will be
                converted to :py:class:`Version`
        """

        if not isinstance(series, Version):
            series = Version(series)
        if self in {self.lowest(), self.latest()}:
            if series == self:
                return True
            else:
                return False
        return series.version == self.version[:len(series.version)]

    def series(self, n=2):
        """Returns the series (first ``n`` items) of the version

        Args:
            n: How many version components to include.

        Returns:
            :py:class:`str`
        """
        return ".".join(self.vstring.split(".")[:n])


class ConstructorResolvable(object):
    """Base class for objects that should be resolvable inside constructors of Widgets etc."""

    def resolve(self, parent_object):
        raise NotImplementedError(
            'You need to implement .resolve(parent_object) on {}'.format(type(self).__name__))


class VersionPick(Widgetable, ConstructorResolvable):
    """A class that implements the version picking functionality.

    Basic usage is a descriptor in which you place instances of :py:class:`VersionPick` in a view.
    Whenever is this instance accessed from an instance, it automatically picks the correct variant
    based on product_version defined in the :py:class:`widgetastic.browser.Browser`.

    You can also use this separately using the :py:meth:`pick` method.

    Example:

    .. code-block:: python

        class MyView(View):
            something_version_dependent = VersionPick({
                '1.0.0': Foo('bar'),
                '2.5.0': Bar('baz'),
            })

    This sample will resolve the correct (Foo or Bar) kind of item and returns it.

    Args:
        version_dict: Dictionary of ``version_introduced: item``
    """

    #: This variable specifies the class that is used for version comparisons. You can replace it
    #: with your own if the new class can be used in </> comparison.
    VERSION_CLASS = Version

    def __init__(self, version_dict):
        if not version_dict:
            raise ValueError('Passed an empty version pick dictionary.')
        self.version_dict = version_dict

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, repr(self.version_dict))

    @property
    def child_items(self):
        return self.version_dict.values()

    def pick(self, version):
        """Selects the appropriate value for given version.

        Args:
            version: A :py:class:`Version` or anything that :py:class:`Version` can digest.

        Returns:
            A value from the version dictionary.
        """
        # convert keys to Versions
        v_dict = {self.VERSION_CLASS(k): v for k, v in self.version_dict.items()}
        versions = v_dict.keys()
        if not isinstance(version, self.VERSION_CLASS):
            version = self.VERSION_CLASS(version)
        sorted_matching_versions = sorted([v for v in versions if v <= version], reverse=True)
        if sorted_matching_versions:
            return v_dict.get(sorted_matching_versions[0])
        else:
            raise ValueError(
                'When trying to version pick {!r} in {!r}, matching version was not found'.format(
                    version, versions))

    def __get__(self, o, type=None):
        if o is None:
            # On a class, therefore not resolving
            return self

        result = self.pick(o.browser.product_version)
        if isinstance(result, Widgetable):
            # Resolve it instead of the class
            return result.__get__(o)
        else:
            return result

    def resolve(self, parent_object):
        return self.__get__(parent_object)


class Fillable(object):
    @classmethod
    def coerce(cls, o):
        """This method serves as a processor for filling values.

        When you are filling values inside widgets and views, I bet you will quickly realize that
        filling basic values like strings or numbers is not enough. This method allows a potential
        fillable implement :py:meth:`as_fill_value` to return a basic value that represents the
        object in the UI

        Args:
            o: Object to be filled in the :py:class:`widgetastic.widget.View` or
                :py:class:`widgetastic.widget.Widget`

        Returns:
            Whatever is supposed to be filled in the widget.
        """
        if isinstance(o, cls):
            return o.as_fill_value()
        else:
            return o

    def as_fill_value(self):
        raise NotImplementedError('Descendants of Fillable must implement .as_fill_value method!')


class ParametrizedString(ConstructorResolvable):
    """Class used to generate strings based on the context passed to the view.

    Useful for parametrized views.

    Supported filters: ``quote`` (XPath)

    Args:
        template: String template in ``.format()`` format, use pipe to add a filter.
    """
    def __init__(self, template):
        self.template = template
        formatter = string.Formatter()
        self.format_params = {}
        for _, param_name, _, _ in formatter.parse(self.template):
            if param_name is None:
                continue
            param = param_name.split('|', 1)
            if len(param) == 1:
                self.format_params[param_name] = (param[0], ())
            else:
                context_var_name = param[0]
                ops = param[1].split('|')
                self.format_params[param_name] = (context_var_name, tuple(ops))

    def resolve(self, view):
        format_dict = {}
        for format_key, (context_name, ops) in self.format_params.items():
            try:
                if context_name.startswith('@'):
                    param_value = getattr(view, context_name[1:])
                else:
                    param_value = view.context[context_name]
            except AttributeError:
                if context_name.startswith('@'):
                    raise AttributeError(
                        'Parameter {} is not present in the object'.format(context_name))
                else:
                    raise TypeError('Parameter class must be defined on a view!')
            except KeyError:
                raise AttributeError(
                    'Parameter {} is not present in the context'.format(context_name))
            for op in ops:
                if op == 'quote':
                    param_value = xpath.quote(param_value)
                else:
                    raise NameError('Unknown operation {} for {}'.format(op, format_key))

            format_dict[format_key] = param_value

        return self.template.format(**format_dict)

    def __get__(self, o, t=None):
        if o is None:
            return self

        return self.resolve(o)


class ParametrizedLocator(ParametrizedString):
    def __get__(self, o, t=None):
        result = super(ParametrizedLocator, self).__get__(o, t)
        if isinstance(result, ParametrizedString):
            return result
        else:
            return Locator(result)


class Parameter(ParametrizedString):
    """Class used to expose a context parameter as an object attribute.

    Args:
        param: Name of the param.
    """
    def __init__(self, param):
        super(Parameter, self).__init__('{' + param + '}')


def _prenormalize_text(text):
    """Makes the text lowercase and removes all characters that are not digits, alphas, or spaces"""
    # _'s represent spaces so convert those to spaces too
    return re.sub(r"[^a-z0-9 ]", "", text.strip().lower().replace('_', ' '))


def _replace_spaces_with(text, delim):
    """Contracts spaces into one character and replaces it with a custom character."""
    return re.sub(r"\s+", delim, text)


def attributize_string(text):
    """Converts a string to a lowercase string containing only letters, digits and underscores.

    Usable for eg. generating object key names.
    The underscore is always one character long if it is present.
    """
    return _replace_spaces_with(_prenormalize_text(text), '_')


def normalize_space(text):
    """Works in accordance with the XPath's normalize-space() operator.

    `Description <https://developer.mozilla.org/en-US/docs/Web/XPath/Functions/normalize-space>`_:

        *The normalize-space function strips leading and trailing white-space from a string,
        replaces sequences of whitespace characters by a single space, and returns the resulting
        string.*
    """
    return _replace_spaces_with(text.strip(), ' ')
