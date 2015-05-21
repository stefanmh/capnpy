import struct
from pypytools.jitview import Color
from capnpy.ptr import Ptr, StructPtr, ListPtr, FarPtr

COLORS = [Color.darkred, Color.darkgreen, Color.brown,
          Color.darkblue, Color.purple, Color.teal]

def print_buffer(buf, **kwds):
    p = BufferPrinter(buf)
    p.printbuf(end=None, **kwds)

class BufferPrinter(object):

    def __init__(self, buf):
        self.buf = buf

    def pyrepr(self, s):
        ch = s[0]
        if ch.isalnum():
            return repr(s)
        else:
            body = ''.join((r'\x%02x' % ord(ch)) for ch in s)
            return "'%s'" % body

    def hex(self, s):
        digits = []
        for ch in s:
            if ch == '\x00':
                digits.append(Color.set(Color.lightgray, '00'))
            else:
                digits.append('%02X' % ord(ch))
        return ' '.join(digits)

    def addr(self, x):
        color = (x/8) % len(COLORS)
        color = COLORS[color]
        return Color.set(color, '%d' % x)

    def string(self, s):
        def printable(ch):
            if 32 <= ord(ch) <= 127:
                return ch
            else:
                return '.'
        return ''.join(map(printable, s))

    def int64(self, s):
        val = struct.unpack('q', s)[0]
        if val < 65536:
            return str(val)
        else:
            return Color.set(Color.lightgray, str(val))

    def double(self, s):
        d = struct.unpack('d', s)[0]
        s = '%9.2f' % d
        if len(s) > 8:
            return Color.set(Color.lightgray, '%.2E' % d)
        else:
            return s

    def ptr(self, offset, s):
        p = Ptr.from_bytes(s)
        try:
            p = p.specialize()
        except ValueError:
            return ' ' * 23
        #
        # try to display only "reasonable" ptrs; if the fields are too big, it
        # probably means that the current word is not a pointer
        def if_in_range(x, min, max):
            if min <= x < max:
                return str(x)
            else:
                return '?'
        #
        if p == 0:
            return  'NULL'.ljust(23)
        if p.kind == StructPtr.KIND:
            descr = 'struct {:>3} {:>2}'.format(if_in_range(p.data_size, 0, 100),
                                                if_in_range(p.ptrs_size, 0, 100))

        elif p.kind == ListPtr.KIND:
            descr = 'list {:>5} {:>2}'.format(if_in_range(p.item_count, 0, 65536),
                                              if_in_range(p.size_tag, 0, 8))

        elif p.kind == FarPtr.KIND:
            descr = 'far {:>6} {:>2}'.format(p.landing_pad,
                                             if_in_range(p.target, 0, 100))
        else:
            descr = 'unknown ptr '
        #
        if -1000 < p.offset < 1000:
            dest = p.deref(offset)
            dest = self.addr(dest)
            dest = dest.ljust(16)
        else:
            dest = '?     '
        line = '{0} to {1}'.format(descr, dest)
        if '?' in line:
            return Color.set(Color.lightgray, line)
        else:
            return line

    def line(self, offset, line):
        addr = self.addr(offset)
        hex = self.hex(line)
        string = self.string(line)
        int64 = self.int64(line)
        double = self.double(line)
        ptr = self.ptr(offset, line)
        # addr is aligned to 16 because 11 chars are ANSI codes for setting colors
        fmt = '{addr:>16}:  {hex}  {string:>8}  {ptr} {double}  {int64}'
        return fmt.format(**locals())

    def printbuf(self, start=0, end=None, human=True):
        if human:
            fmt = '{addr:>5}  {hex:24}  {string:8}  {ptr:21} {double:>11}  {int64}'
            header = fmt.format(addr='Offset', hex=' Hex view', string='ASCII',
                                ptr='Pointer', double='double', int64='int64')
            print Color.set(Color.yellow, header)

        if end is None:
            end = len(self.buf)
        for i in range(start/8, end/8):
            addr = i*8
            line = self.buf[i*8:i*8+8]
            if human:
                print self.line(addr, line)
            else:
                print '%5d: %s' % (addr, self.pyrepr(line))


if __name__ == '__main__':
    buf = ('\x04\x00\x00\x00\x02\x00\x00\x00'    # ptr to a
           '\x08\x00\x00\x00\x02\x00\x00\x00'    # ptr to b
           '\x01\x00\x00\x00\x00\x00\x00\x00'    # a.x == 1
           '\x02\x00\x00\x00\x00\x00\x00\x00'    # a.y == 2
           '\x03\x00\x00\x00\x00\x00\x00\x00'    # b.x == 3
           '\x04\x00\x00\x00\x00\x00\x00\x00'    # b.y == 4
           '\x01\x00\x00\x00\x82\x00\x00\x00'    # ptrlist
           'hello capnproto\0')                  # string

    p = BufferPrinter(buf)
    p.printbuf(8, 40)