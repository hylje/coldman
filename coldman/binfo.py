"""Blockchain.info API wrapper"""

class Binfo(object):
    def __init__(self, connection_string):
        self._binfo = jsonrpc.ServiceProxy(connection_string)
    
    def multiaddr(self, addresses):
        return self._binfo.multiaddr(active="|".join(addresses))
