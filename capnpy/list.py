import struct
import capnpy
from capnpy.blob import Blob, Types
from capnpy.ptr import Ptr, StructPtr, ListPtr
from capnpy import listbuilder

class List(object):

    @classmethod
    def from_buffer(cls, buf, offset, size_tag, item_count, item_type):
        """
        buf, offset: the underlying buffer and the offset where the list starts

        item_length: the length of each list item, in BYTES. Note: this is NOT the
        value of the ListPtr.SIZE_* tag, although it's obviously based on it

        item_type: the type of each list item. Either a Blob/Struct subclass,
        or a Types.*
        """
        self = cls.__new__(cls)
        self._blob = Blob(buf, offset)
        self._item_type = item_type
        self._set_list_tag(size_tag, item_count)
        return self

    def _set_list_tag(self, size_tag, item_count):
        self._size_tag = size_tag
        if size_tag == ListPtr.SIZE_COMPOSITE:
            tag = self._blob._buf.read_primitive(self._blob._offset, Types.int64)
            tag = StructPtr(tag)
            self._tag = tag
            self._item_count = tag.offset
            self._item_length = (tag.data_size+tag.ptrs_size)*8
            self._item_offset = 8
        elif size_tag == ListPtr.SIZE_BIT:
            raise ValueError('Lists of bits are not supported')
        else:
            self._tag = None
            self._item_count = item_count
            self._item_length = ListPtr.SIZE_LENGTH[size_tag]
            self._item_offset = 0

    def __repr__(self):
        return '<capnpy list [%d items]>' % (len(self),)

    def _read_list_item(self, offset):
        raise NotImplementedError

    def _get_offset_for_item(self, i):
        return self._item_offset + (i*self._item_length)
            
    def __len__(self):
        return self._item_count

    def __getitem__(self, i):
        if isinstance(i, slice):
            idx = xrange(*i.indices(len(self)))
            return [self._getitem_fast(j) for j in idx]
        if i < 0:
            i += self._item_count
        if 0 <= i < self._item_count:
            return self._getitem_fast(i)
        raise IndexError

    def _getitem_fast(self, i):
        """
        WARNING: no bound checks!
        """
        offset = self._get_offset_for_item(i)
        return self._read_list_item(offset)


    def _get_body_range(self):
        return self._get_body_start(), self._get_body_end()

    def _get_body_start(self):
        return self._blob._offset

    def _get_body_end(self):
        if self._size_tag == ListPtr.SIZE_COMPOSITE:
            return self._get_body_end_composite()
        elif self._size_tag == ListPtr.SIZE_PTR:
            return self._get_body_end_ptr()
        else:
            return self._get_body_end_scalar()

    def _get_body_end_composite(self):
        # lazy access to Struct to avoid circular imports
        Struct = capnpy.struct_.Struct
        #
        # to calculate the end the of the list, there are three cases
        #
        # 1) if the items has no pointers, the end of the list correspond
        #    to the end of the items
        #
        # 2) if they HAVE pointers but they are ALL null, it's the same as (1)
        #
        # 3) if they have pointers, the end of the list is at the end of
        #    the extra of the latest item having a pointer field set

        if self._tag.ptrs_size == 0:
            # case 1
            return self._get_body_end_scalar() # +8 is for the tag

        i = self._item_count-1
        while i >= 0:
            struct_offset = self._get_offset_for_item(i)
            struct_offset += self._blob._offset
            mystruct = Struct.from_buffer(self._blob._buf,
                                          struct_offset,
                                          self._tag.data_size,
                                          self._tag.ptrs_size)
            end = mystruct._get_extra_end_maybe()
            if end is not None:
                # case 3
                return end
            i -= 1

        # case 2
        return self._get_body_end_scalar()+8 # +8 is for the tag

    def _get_body_end_ptr(self):
        ptr_offset = self._get_offset_for_item(self._item_count-1)
        blob = self._blob._read_list_or_struct(ptr_offset)
        return blob._get_end()

    def _get_body_end_scalar(self):
        return self._blob._offset + self._item_length*self._item_count

    def _get_end(self):
        return self._get_body_end()

    def _get_key(self):
        start, end = self._get_body_range()
        body = self._blob._buf.s[start:end]
        return (self._item_count, self._item_type, body)

    def __eq__(self, other):
        if isinstance(other, list):
            return list(self) == other
        if self.__class__ is not other.__class__:
            return False
        return self._get_key() == other._get_key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        raise TypeError, "capnpy lists can be compared only for equality"

    __le__ = __lt__
    __gt__ = __lt__
    __ge__ = __lt__


class PrimitiveList(List):
    ItemBuilder = listbuilder.PrimitiveItemBuilder
    
    def _read_list_item(self, offset):
        buf = self._blob._buf
        return buf.read_primitive(self._blob._offset+offset, self._item_type)

class StructList(List):
    ItemBuilder = listbuilder.StructItemBuilder

    def _read_list_item(self, offset):
        return self._item_type.from_buffer(self._blob._buf,
                                           self._blob._offset+offset,
                                           self._tag.data_size,
                                           self._tag.ptrs_size)


class StringList(List):
    ItemBuilder = listbuilder.StringItemBuilder

    def _read_list_item(self, offset):
        return self._blob._read_string(offset)

