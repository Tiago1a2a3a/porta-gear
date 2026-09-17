import socket
import struct
import time

def get_ntp_time(host="pool.ntp.org"):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(3.0)
        data = b'\x1b' + 47 * b'\0'
        client.sendto(data, (host, 123))
        data, address = client.recvfrom(1024)
        if data:
            t = struct.unpack('!12I', data)[10]
            t -= 2208988800
            return time.ctime(t)
    except Exception as e:
        return str(e)
print(get_ntp_time())
