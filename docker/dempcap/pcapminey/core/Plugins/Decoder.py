# -*- coding: utf8 -*-
__author__ = 'Viktor Winkelmann'

from abc import ABCMeta, abstractmethod, abstractproperty
from Plugin import *

class Decoder(Plugin):
    __metaclass__ = ABCMeta

    @abstractproperty
    def decoderName(self):
        """ IMPORTANT: Override as Class Property """
        return NotImplemented    
    
    @classmethod
    def getPriority(cls):
        return cls.basePriority

    @abstractmethod
    def decodeData(self, data):
        """ IMPORTANT: Override as Class Method (using @classmethod) """
        return NotImplemented
