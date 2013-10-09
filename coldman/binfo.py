"""Blockchain.info API wrapper"""

from bitcoinrpc import authproxy

class Binfo(object):
    def __init__(self, connection_string):
        self._binfo = authproxy.AuthServiceProxy(connection_string)
    
    def multiaddr(self, addresses):
        return self._binfo.multiaddr(active="|".join(addresses))
