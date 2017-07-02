import socket
import sys
import struct
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from time import time
from select import select


NTP_CURRENT_VERSION = 4
NTP_HEADER = '>BBBBIi4sQQQQ'
NTP_UTC_OFFSET = 2208988800


def utc_to_ntp_bytes(time):
    return int((Decimal(time) + NTP_UTC_OFFSET) * (2 ** 32))


class Packet:
    def __init__(self, leap=0, vn=NTP_CURRENT_VERSION, mode=4, stratum=1, poll=0, precision=0,
                 root_delay=0, root_dispersion=0, ref_id=b'\x00' * 4, ref_time=0, origin=0,
                 receive=0, transmit=0):
        self.leap = leap
        self.version = vn
        self.mode = mode
        self.option = (self.leap << 6) | (self.version << 3) | self.mode
        self.stratum = stratum
        self.poll = poll
        self.precision = precision
        self.root_delay = root_delay
        self.root_dispersion = root_dispersion
        self.ref_id = ref_id
        self.ref_time = ref_time
        self.origin = origin
        self.receive = receive
        self.transmit = transmit

    @staticmethod
    def from_binary(data):
        try:
            option, stratum, poll, prescision, root_delay, \
                root_description, ref_id, ref_time, origin, receive, transmit = \
                struct.unpack(NTP_HEADER,
                              data[:struct.calcsize(NTP_HEADER)])
        except struct.error:
            pass
        leap, version, mode = option >> 6, ((option >> 3) & 0x7), option & 0x7
        return Packet(leap, version, mode, stratum, poll, prescision,
                      root_delay, root_description, ref_id,
                      ref_time, origin, receive, transmit)

    def to_binary(self):
        return struct.pack(NTP_HEADER,
                           self.option,
                           self.stratum,
                           self.poll,
                           self.precision,
                           self.root_delay,
                           self.root_dispersion,
                           self.ref_id,
                           self.ref_time,
                           self.origin,
                           self.receive,
                           self.transmit)


class SNTPServer:
    def __init__(self, delay, port):
        if port:
            self.port = port
        else:
            self.port = 123
        if delay:
            self.delay = delay
        else:
            self.delay = 0

    def run(self, prefix):
        print('Server start')
        server_address = (prefix, self.port)
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(server_address)

        with ThreadPoolExecutor(max_workers=20) as executor:
            while True:
                if select([server], [], [], 2)[0]:
                    data, addr = server.recvfrom(1024)
                    receive_time = utc_to_ntp_bytes(time() + self.delay)
                    print('Connected: {}'.format(addr))
                    executor.submit(self.client_thread, data, receive_time, addr, server)

    def client_thread(self, data, receive_time, addr, sock):
            if select([], [sock], [], 3)[1]:
                current_time = utc_to_ntp_bytes(time() + self.delay)
                responce = self.struct_package(
                    receive_time, current_time, recv_data=data)
                sock.sendto(responce, addr)

    def struct_package(self, receive_timestamp, transmit_timestamp,
                       *, recv_data=None, li=3, mode=4):
        recv_pack = Packet.from_binary(recv_data)
        vn = recv_pack.version
        stratum = 0
        poll = recv_pack.poll
        precision = 0
        root_delay = 0
        root_dispersion = 0
        ref_ident = b'LOCL'
        ref_timestamp = transmit_timestamp
        origin_timestamp = recv_pack.transmit
        transmit = transmit_timestamp
        receive = receive_timestamp
        return Packet(li, vn, mode, stratum,
                      poll, precision, root_delay, root_dispersion,
                      ref_ident, ref_timestamp, origin_timestamp,
                      receive, transmit).to_binary()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=int, action='store', dest='delay')
    parser.add_argument('-p', '--port', type=int, action='store', dest='port')
    args = parser.parse_args(sys.argv[1:])
    server = SNTPServer(delay=args.delay, port=args.port)
    server.run('localhost')
