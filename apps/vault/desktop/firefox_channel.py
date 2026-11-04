"""Load the same bounded Noise implementation used by Firefox."""

import ctypes as ffi

BUFFER_SIZE = 16 * 1024


class ChannelError(ValueError):
    pass


class ChannelLibrary:
    def __init__(self, path):
        self.dll = ffi.CDLL(str(path))
        for name, args, result in (
            ('new', [], ffi.c_void_p),
            ('buffer', [ffi.c_void_p], ffi.c_void_p),
            ('free', [ffi.c_void_p], None),
            ('start', [ffi.c_void_p, ffi.c_uint32, ffi.c_uint32], ffi.c_int32),
            ('step', [ffi.c_void_p, ffi.c_uint32, ffi.c_size_t], ffi.c_int32),
        ):
            function = getattr(self.dll, 'vault_channel_' + name)
            function.argtypes = args
            function.restype = result
            setattr(self, name, function)


class Channel:
    def __init__(self, library):
        self.library = library
        self.handle = library.new()
        self.buffer = library.buffer(self.handle)

    def start(self, key, pairing, *, initiator=False):
        if len(key) != 32:
            raise ChannelError('Invalid pairing key')
        ffi.memmove(self.buffer, key, len(key))
        return self.result(self.library.start(self.handle, int(initiator), int(pairing)))

    def step(self, operation, value):
        if len(value) > BUFFER_SIZE:
            raise ChannelError('Invalid message size')
        ffi.memmove(self.buffer, value, len(value))
        return self.result(self.library.step(self.handle, operation, len(value)))

    def result(self, length):
        if not 0 <= length <= BUFFER_SIZE:
            raise ChannelError('Invalid encrypted Firefox message')
        data = ffi.string_at(self.buffer, length)
        ffi.memset(self.buffer, 0, length)
        return data

    def close(self):
        if self.handle:
            self.library.free(self.handle)
            self.handle = None
