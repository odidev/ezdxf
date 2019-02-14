# Copyright (c) 2019 Manfred Moitzi
# License: MIT License
# Created 2019-02-13
#
# DXFEntity - Root Entity
# DXFObject - non graphical entities stored in OBJECTS section
# DXFGraphical - graphical DXF entities stored in ENTITIES and BLOCKS sections
#
from typing import TYPE_CHECKING, List, cast, Union, Iterable, Set, Sequence
from collections import OrderedDict
from ezdxf.lldxf.types import dxftag, uniform_appid
from ezdxf.lldxf.tags import Tags
from ezdxf.lldxf.const import DXFKeyError, DXFStructureError
from ezdxf.lldxf.const import ACAD_XDICTIONARY, ACAD_REACTORS, XDICT_HANDLE_CODE, REACTOR_HANDLE_CODE, APP_DATA_MARKER
from ezdxf.clone import clone

if TYPE_CHECKING:
    from ezdxf.lldxf.tagwriter import TagWriter
    from ezdxf.eztypes import DXFDictionary, Drawing
    from ezdxf.entities.dxfentity import DXFEntity

ERR_INVALID_DXF_ATTRIB = 'Invalid DXF attribute for entity {}'
ERR_DXF_ATTRIB_NOT_EXITS = 'DXF attribute {} does not exist'


class AppData:
    def __init__(self):
        # no back links, no self.clone() required
        self.data = OrderedDict()

    def __contains__(self, appid: str) -> bool:
        return uniform_appid(appid) in self.data

    def __len__(self) -> int:
        return len(self.data)

    def get(self, appid: str) -> Tags:
        try:
            return self.data[uniform_appid(appid)]
        except KeyError:
            raise DXFKeyError(appid)

    def set(self, tags: Tags) -> None:
        if len(tags):
            appid = tags[0].value
            self.data[appid] = tags

    def add(self, appid: str, data: Iterable[Sequence]) -> None:
        data = Tags(dxftag(code, value) for code, value in data)
        appid = uniform_appid(appid)
        if data[0] != (APP_DATA_MARKER, appid):
            data.insert(0, dxftag(APP_DATA_MARKER, appid))
        if data[-1] != (APP_DATA_MARKER, '}'):
            data.append(dxftag(APP_DATA_MARKER, '}'))
        self.set(data)

    def discard(self, appid: str):
        _appid = uniform_appid(appid)
        if _appid in self.data:
            del self.data[_appid]

    def export_dxf(self, tagwriter: 'TagWriter') -> None:
        for data in self.data.values():
            tagwriter.write_tags(data)


class Reactors:
    """ Handle storage for related reactors.

    Reactors are other objects related to the object that contains this Reactor() instance.

    """

    def __init__(self, handles: Iterable[str] = None):
        # no back links, no self.clone() required
        self.reactors = None  # type: Set[str]  # stores handle strings
        self.set(handles)

    def __len__(self) -> int:
        return len(self.reactors)

    def __contains__(self, handle):
        return handle in self.reactors

    @classmethod
    def from_tags(cls, tags: Tags = None) -> 'Reactors':
        """
        Create Reactors() instance from tags.

        Expected DXF structure: [(102, '{ACAD_REACTORS'), (330, handle), ...,(102, '}')]

        Args:
            tags: list of DXFTags()

        """
        if tags is None:
            return cls(None)

        if len(tags) < 3:
            raise DXFStructureError("ACAD_REACTORS error")
        return cls((handle.value for handle in tags[1:-1]))

    def get(self) -> List[str]:
        return sorted(self.reactors)

    def set(self, handles: Iterable[str]) -> None:
        self.reactors = set(handles or [])

    def add(self, handle: str) -> None:
        self.reactors.add(handle)

    def discard(self, handle: str):
        self.reactors.discard(handle)

    def export_dxf(self, tagwriter: 'TagWriter') -> None:
        tagwriter.write_tag2(APP_DATA_MARKER, ACAD_REACTORS)
        for handle in self.get():
            tagwriter.write_tag2(REACTOR_HANDLE_CODE, handle)
        tagwriter.write_tag2(APP_DATA_MARKER, '}')


class ExtensionDict:
    # todo: test, but requires objects section
    def __init__(self, owner: 'DXFEntity' = None, handle=None):
        # back link owner, so __clone__() necessary
        self.owner = owner
        # _dict is None -> empty dict
        # _dict as string -> handle to dict
        # _dict as DXFDictionary
        self._xdict = handle  # type: Union[str, DXFDictionary, None]

    def clone(self):
        # set owner to None, because actual owner is not the owner of the copied extension dict for sure.
        # using clone() for safety reason
        return self.__class__(None, clone(self._xdict))

    @classmethod
    def from_tags(cls, entity: 'DXFEntity', tags: Tags = None):
        if tags is None:
            return cls(entity, None)

        # expected DXF structure: [(102, '{ACAD_XDICTIONARY', (360, handle), (102, '}')]
        if len(tags) != 3 or tags[1].code != XDICT_HANDLE_CODE:
            raise DXFStructureError("ACAD_XDICTIONARY error in entity: " + str(entity))
        return cls(entity, tags[1].value)

    @property
    def doc(self) -> 'Drawing':
        return self.owner.doc

    def get(self) -> 'DXFDictionary':
        """
        Get associated extension dictionary as DXFDictionary() object.

        """
        if self._xdict is None:
            self._xdict = self._new()
        elif isinstance(self._xdict, str):
            # replace handle string by DXFDictionary object
            self._xdict = cast('DXFDictionary', self.owner.entitydb.get(self._xdict))
        return self._xdict

    def _new(self) -> 'DXFDictionary':
        xdict = self.doc.objects.add_dictionary(owner=self.owner.dxf.handle)
        return cast('DXFDictionary', xdict)

    def export_dxf(self, tagwriter: 'TagWriter') -> None:
        xdict = self._xdict
        if xdict is None:
            return
        handle = xdict if isinstance(xdict, str) else xdict.dxf.handle
        tagwriter.write_tag2(APP_DATA_MARKER, ACAD_XDICTIONARY)
        tagwriter.write_tag2(XDICT_HANDLE_CODE, handle)
        tagwriter.write_tag2(APP_DATA_MARKER, '}')
