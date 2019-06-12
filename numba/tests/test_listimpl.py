"""
Testing C implementation of the numba list
"""
from __future__ import print_function, absolute_import, division

import ctypes
import struct

from .support import TestCase
from numba import _helperlib
from numba.config import IS_32BITS


LIST_OK = 0
LIST_ERR_INDEX = -1
LIST_ERR_NO_MEMORY = -2
LIST_ERR_MUTATED = -3
LIST_ERR_ITER_EXHAUSTED = -4


class List(object):
    """A wrapper around the C-API to provide a minimal list object for
    testing.
    """
    def __init__(self, tc, itemsize, allocated):
        """
        Parameters
        ----------
        tc : TestCase instance
        itemsize : int
            byte size for the items
        """
        self.tc = tc
        self.itemsize = itemsize
        self.allocated = allocated
        self.lp = self.list_new(itemsize, allocated)

    def __del__(self):
        self.tc.numba_list_free(self.lp)

    def __len__(self):
        return self.list_length()

    def __setitem__(self, i, item):
        return self.list_setitem(i, item)

    def __getitem__(self, i):
        return self.list_getitem(i)

    def __iter__(self):
        return ListIter(self)

    def append(self, item):
        self.list_append(item)

    def pop(self, i=None):
        return self.list_pop(i)

    def list_new(self, itemsize, allocated):
        lp = ctypes.c_void_p()
        status = self.tc.numba_list_new(
            ctypes.byref(lp), itemsize, allocated,
        )
        self.tc.assertEqual(status, LIST_OK)
        return lp

    def list_length(self):
        return self.tc.numba_list_length(self.lp)

    def list_setitem(self, i, item):
        status = self.tc.numba_list_setitem(self.lp, i, item)
        if status == LIST_ERR_INDEX:
            raise IndexError("list index out of range")

    def list_getitem(self, i):
        item_out_buffer = ctypes.create_string_buffer(self.itemsize)
        status = self.tc.numba_list_getitem(self.lp, i, item_out_buffer)
        if status == LIST_ERR_INDEX:
            raise IndexError("list index out of range")
        else:
            self.tc.assertEqual(status, LIST_OK)
            return item_out_buffer.raw

    def list_append(self, item):
        status = self.tc.numba_list_append(self.lp, item)
        self.tc.assertEqual(status, LIST_OK)

    def list_pop(self, i):
        if i is None:
            i = len(self) - 1
        item_out_buffer = ctypes.create_string_buffer(self.itemsize)
        status = self.tc.numba_list_pop(self.lp, i, item_out_buffer)
        if status == LIST_ERR_INDEX:
            raise IndexError("list index out of range")
        else:
            self.tc.assertEqual(status, LIST_OK)
            return item_out_buffer.raw

    def list_iter(self, itptr):
        self.tc.numba_list_iter(itptr, self.lp)

    def list_iter_next(self, itptr):
        bi = ctypes.c_void_p(0)
        status = self.tc.numba_list_iter_next(
            itptr, ctypes.byref(bi),
        )
        if status == LIST_ERR_MUTATED:
            raise ValueError('list mutated')
        elif status == LIST_ERR_ITER_EXHAUSTED:
            raise StopIteration
        else:
            self.tc.assertGreaterEqual(status, 0)
            item = (ctypes.c_char * self.itemsize).from_address(bi.value)
            return item.value


class ListIter(object):
    """An iterator for the `List`.
    """
    def __init__(self, parent):
        self.parent = parent
        itsize = self.parent.tc.numba_list_iter_sizeof()
        self.it_state_buf = (ctypes.c_char_p * itsize)(0)
        self.it = ctypes.cast(self.it_state_buf, ctypes.c_void_p)
        self.parent.list_iter(self.it)

    def __iter__(self):
        return self

    def __next__(self):
        return self.parent.list_iter_next(self.it)

    next = __next__    # needed for py2 only


class TestListImpl(TestCase):
    def setUp(self):
        """Bind to the c_helper library and provide the ctypes wrapper.
        """
        list_t = ctypes.c_void_p
        iter_t = ctypes.c_void_p

        def wrap(name, restype, argtypes=()):
            proto = ctypes.CFUNCTYPE(restype, *argtypes)
            return proto(_helperlib.c_helpers[name])

        # numba_test_list()
        self.numba_test_list = wrap(
            'test_list',
            ctypes.c_int,
        )

        # numba_list_new(NB_List *l, Py_ssize_t itemsize, Py_ssize_t allocated)
        self.numba_list_new = wrap(
            'list_new',
            ctypes.c_int,
            [ctypes.POINTER(list_t), ctypes.c_ssize_t, ctypes.c_ssize_t],
        )
        # numba_list_free(NB_List *l)
        self.numba_list_free = wrap(
            'list_free',
            None,
            [list_t],
        )
        # numba_list_length(NB_List *l)
        self.numba_list_length = wrap(
            'list_length',
            ctypes.c_int,
            [list_t],
        )
        # numba_list_setitem(NB_List *l, Py_ssize_t i, const char *item)
        self.numba_list_setitem = wrap(
            'list_setitem',
            ctypes.c_int,
            [list_t, ctypes.c_ssize_t, ctypes.c_char_p],
        )
        # numba_list_append(NB_List *l, const char *item)
        self.numba_list_append = wrap(
            'list_append',
            ctypes.c_int,
            [list_t, ctypes.c_char_p],
        )
        # numba_list_getitem(NB_List *l,  Py_ssize_t i, char *out)
        self.numba_list_getitem = wrap(
            'list_getitem',
            ctypes.c_int,
            [list_t, ctypes.c_ssize_t, ctypes.c_char_p],
        )
        # numba_list_pop(NB_List *l,  Py_ssize_t i, char *out)
        self.numba_list_pop = wrap(
            'list_pop',
            ctypes.c_int,
            [list_t, ctypes.c_ssize_t, ctypes.c_char_p],
        )
        # numba_list_iter_sizeof()
        self.numba_list_iter_sizeof = wrap(
            'list_iter_sizeof',
            ctypes.c_size_t,
        )
        # numba_list_iter(
        #     NB_ListIter *it,
        #     NB_List     *l
        # )
        self.numba_list_iter = wrap(
            'list_iter',
            None,
            [
                iter_t,
                list_t,
            ],
        )
        # numba_list_iter_next(
        #     NB_ListIter *it,
        #     const char **item_ptr,
        # )
        self.numba_list_iter_next = wrap(
            'list_iter_next',
            ctypes.c_int,
            [
                iter_t,                             # it
                ctypes.POINTER(ctypes.c_void_p),    # item_ptr
            ],
        )

    def test_simple_c_test(self):
        # Runs the basic test in C.
        ret = self.numba_test_list()
        self.assertEqual(ret, 0)

    def test_length(self):
        l = List(self, 8, 0)
        self.assertEqual(len(l), 0)

    def test_append_get_string(self):
        l = List(self, 8, 1)
        l.append(b"abcdefgh")
        self.assertEqual(len(l), 1)
        r = l[0]
        self.assertEqual(r, b"abcdefgh")

    def test_append_get_int(self):
        l = List(self, 8, 1)
        l.append(struct.pack("q", 1))
        self.assertEqual(len(l), 1)
        r = struct.unpack("q", l[0])[0]
        self.assertEqual(r, 1)

    def test_append_get_string_realloc(self):
        l = List(self, 8, 1)
        l.append(b"abcdefgh")
        self.assertEqual(len(l), 1)
        l.append(b"hijklmno")
        self.assertEqual(len(l), 2)
        r = l[1]
        self.assertEqual(r, b"hijklmno")

    def test_set_item_getitem_index_error(self):
        l = List(self, 8, 0)
        with self.assertRaises(IndexError):
            l[0]
        with self.assertRaises(IndexError):
            l[0] = b"abcdefgh"

    def test_iter(self):
        l = List(self, 1, 0)
        values = [b'a', b'b', b'c', b'd', b'e', b'f', b'g', b'h']
        for i in values:
            l.append(i)
        received = []
        for j in l:
            received.append(j)
        self.assertEqual(values, received)

    def test_pop(self):
        l = List(self, 1, 0)
        values = [b'a', b'b', b'c', b'd', b'e', b'f', b'g', b'h']
        for i in values:
            l.append(i)
        self.assertEqual(len(l), 8)

        received = l.pop()
        self.assertEqual(b'h', received)
        self.assertEqual(len(l), 7)
        received = [j for j in l]
        self.assertEqual(received, values[:-1])

        received = l.pop(0)
        self.assertEqual(b'a', received)
        self.assertEqual(len(l), 6)

        received = l.pop(2)
        self.assertEqual(b'd', received)
        self.assertEqual(len(l), 5)

        expected = [b'b', b'c', b'e', b'f', b'g']
        received = [j for j in l]
        self.assertEqual(received, expected)

    def test_pop_byte(self):
        l = List(self, 4, 0)
        values = [b'aaaa', b'bbbb', b'cccc', b'dddd',
                  b'eeee', b'ffff', b'gggg', b'hhhhh']
        for i in values:
            l.append(i)
        self.assertEqual(len(l), 8)

        received = l.pop()
        self.assertEqual(b'hhhh', received)
        self.assertEqual(len(l), 7)
        received = [j for j in l]
        self.assertEqual(received, values[:-1])

        received = l.pop(0)
        self.assertEqual(b'aaaa', received)
        self.assertEqual(len(l), 6)

        received = l.pop(2)
        self.assertEqual(b'dddd', received)
        self.assertEqual(len(l), 5)

        expected = [b'bbbb', b'cccc', b'eeee', b'ffff', b'gggg']
        received = [j for j in l]
        self.assertEqual(received, expected)
