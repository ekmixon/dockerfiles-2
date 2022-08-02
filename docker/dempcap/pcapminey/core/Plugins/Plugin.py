# -*- coding: utf8 -*-
__author__ = 'Viktor Winkelmann'

from abc import ABCMeta, abstractmethod

class Plugin:
    __metaclass__ = ABCMeta

    basePriority = 50

    @abstractmethod
    def getPriority(self):
        """ IMPORTANT: Override as Class Method (using @classmethod) """
        return NotImplemented