"""Lossless PNG encoder; stdlib + NumPy only."""
import struct
import zlib
import numpy as np

def png(array):
    array = np.asarray(array)
    if array.dtype == np.dtype('uint16') and array.ndim == 2:
        bits, color, pixels = 16, 0, array.astype('>u2').tobytes()
    elif array.dtype == np.dtype('uint8') and array.ndim == 2:
        bits, color, pixels = 8, 0, array.tobytes()
    elif array.dtype == np.dtype('uint8') and array.ndim == 3 and array.shape[2] == 3:
        bits, color, pixels = 8, 2, array.tobytes()
    else:
        raise ValueError('unsupported PNG pixels')
    height, width = array.shape[:2]
    stride = len(pixels)//height
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    scan = b''.join(b'\0'+pixels[i*stride:(i+1)*stride] for i in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,bits,color,0,0,0))
            +chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))


