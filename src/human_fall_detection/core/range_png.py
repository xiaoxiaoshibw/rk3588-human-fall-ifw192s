"""Lossless PNG encoder; stdlib + NumPy only."""
import struct
import zlib
import numpy as np

def png(array, compress_level=6):
    array = np.asarray(array)
    height, width = array.shape[:2]
    if array.dtype == np.dtype('uint16') and array.ndim == 2:
        bits, color = 16, 0
        raw_rows = np.ascontiguousarray(array, dtype='>u2').view(np.uint8).reshape(height, width * 2)
    elif array.dtype == np.dtype('uint8') and array.ndim == 2:
        bits, color = 8, 0
        raw_rows = np.ascontiguousarray(array, dtype=np.uint8).reshape(height, width)
    elif array.dtype == np.dtype('uint8') and array.ndim == 3 and array.shape[2] == 3:
        bits, color = 8, 2
        raw_rows = np.ascontiguousarray(array, dtype=np.uint8).reshape(height, width * 3)
    else:
        raise ValueError('unsupported PNG pixels')
    padded = np.empty((height, raw_rows.shape[1] + 1), dtype=np.uint8)
    padded[:, 0] = 0
    padded[:, 1:] = raw_rows
    scan = padded.tobytes()
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,bits,color,0,0,0))
            +chunk(b'IDAT',zlib.compress(scan, compress_level))+chunk(b'IEND',b''))



