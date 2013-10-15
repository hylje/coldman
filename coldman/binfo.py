"""Blockchain.info API wrapper"""

import requests

class BinfoConnection(object):
    def __init__(self, connection_string):
        self._url = connection_string
    
    def multiaddr(self, active):
        return (requests
                .get(self._url + "multiaddr", 
                     params={"active": "|".join(active)})
                .json())
