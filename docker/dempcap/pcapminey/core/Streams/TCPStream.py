# -*- coding: utf8 -*-
__author__ = 'Viktor Winkelmann'

from cStringIO import StringIO
from contextlib import closing
from PacketStream import *
import dpkt

class TCPStream(PacketStream):
    def __init__(self, ipSrc, portSrc, ipDst, portDst):
        PacketStream.__init__(self, ipSrc, portSrc, ipDst, portDst)

        self.packets = {}

    def __len__(self):
        return len(self.packets)

    def addPacket(self, packet, ts):
        if type(packet) != dpkt.tcp.TCP:
            raise TypeError('Packet is not a TCP packet!')

        if len(packet.data) == 0:
            return

        if packet.seq not in self.packets:
            self.packets[packet.seq] = packet

        if self.tsFirstPacket is None or ts < self.tsFirstPacket:
            self.tsFirstPacket = ts

        if self.tsLastPacket is None or ts > self.tsLastPacket:
            self.tsLastPacket = ts


    def __iter__(self):
        yield from sorted(self.packets.values(), key=lambda v: v.seq)

    def getFirstBytes(self, count):
        with closing(StringIO()) as bytes:
            index = 0
            sortedPackets = sorted(self.packets.values(), key=lambda v: v.seq)
            while len(bytes) < count and index < len(sortedPackets):
                bytes.write(sortedPackets[index].data)
                index += 1

            return bytes.getvalue()[:count]

    def getAllBytes(self):
        with closing(StringIO()) as bytes:
            for packet in self:
                bytes.write(packet.data)

            return bytes.getvalue()

    def isValid(self):
        if len(self.packets) == 0:
            return False

        sortedPackets = sorted(self.packets.values(), key=lambda v: v.seq)
        firstPacket = sortedPackets[0]

        nextSeq = firstPacket.seq + len(firstPacket.data)

        for packet in sortedPackets[1:]:
            if packet.seq != nextSeq:
                return False

            nextSeq += 1 if len(packet.data) == 0 else len(packet.data)
        return True
