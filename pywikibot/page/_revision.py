"""Object representing page revision."""
#
# (C) Pywikibot team, 2008-2022
#
# Distributed under the terms of the MIT license.
#
import hashlib
from collections.abc import Mapping
from contextlib import suppress

from pywikibot import Timestamp, warning
from pywikibot.tools import deprecated


class Revision(Mapping):

    """A structure holding information about a single revision of a Page.

    Each data item can be accessed either by its key or as an attribute
    with the attribute name equal to the key e.g.:

    >>> r = Revision(comment='Sample for Revision access')
    >>> r.comment == r['comment']
    True
    >>> r.comment
    'Sample for Revision access'
    """

    def __init__(self, **kwargs) -> None:
        """Initializer."""
        self._data = kwargs
        self._upcast_dict(self._data)
        super().__init__()

    @staticmethod
    def _upcast_dict(map_) -> None:
        """Upcast dictionary values."""
        with suppress(KeyError):  # enable doctest
            map_['timestamp'] = Timestamp.fromISOformat(map_['timestamp'])

        map_.update(anon='anon' in map_)
        map_.update(minor='minor' in map_)
        map_.update(userhidden='userhidden' in map_)
        map_.update(commenthidden='commenthidden' in map_)

        map_.setdefault('comment', '')
        map_.setdefault('user', '')

        if 'slots' in map_:  # mw 1.32+
            mainslot = map_['slots'].get('main', {})
            map_['text'] = mainslot.get('*')
            map_['contentmodel'] = mainslot.get('contentmodel')
        else:
            map_['slots'] = None
            map_['text'] = map_.get('*')

        map_.setdefault('sha1')
        if map_['sha1'] is None and map_['text'] is not None:
            map_['sha1'] = hashlib.sha1(
                map_['text'].encode('utf8')).hexdigest()

    def __len__(self) -> int:
        """Return the number of data items."""
        return len(self._data)

    def __getitem__(self, name: str):
        """Return a single Revision item given by name."""
        if name in self._data:
            return self._data[name]
        if name in ('parent_id', 'content_model'):
            return getattr(self, name)

        return self.__missing__(name)

    # provide attribute access
    __getattr__ = __getitem__

    def __iter__(self):
        """Provide Revision data as iterator."""
        return iter(self._data)

    def __repr__(self) -> str:
        """String representation of Revision."""
        return '{}({})'.format(self.__class__.__name__, self._data)

    def __str__(self) -> str:
        """Printable representation of Revision data."""
        return str(self._data)

    def __missing__(self, key):
        """Provide backward compatibility for exceptions."""
        if key == 'parentid':
            raise AssertionError(
                'Revision {rev.revid} was instantiated without a parent id'
                .format(rev=self))

        if key == 'rollbacktoken':
            warning('"rollbacktoken" has been deprecated since MediaWiki 1.24')
            return

        # raise AttributeError instead of KeyError for backward compatibility
        raise AttributeError("'{}' object has no attribute '{}'"
                             .format(self.__class__.__name__, key))

    @property
    @deprecated('parentid property', since='4.0.0')
    def parent_id(self) -> int:
        """DEPRECATED. Return id of parent/previous revision.

        Returns 0 if there is no previous revision

        :return: id of parent/previous revision
        :raises AssertionError: parent id not supplied to the constructor
        """
        return self.parentid

    @property
    @deprecated('contentmodel', since='4.0.0')
    def content_model(self) -> str:
        """DEPRECATED. Return content model of the revision.

        This is meant for compatibility with older MW version which
        didn't support revisions with slots. For newer MW versions,
        this returns the content model of the main slot.

        :return: content model
        """
        return self.contentmodel
