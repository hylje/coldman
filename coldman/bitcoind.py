"""Bitcoind RPC"""

from bitcoinrpc import authproxy

class BitcoindConnection(object):
    def __init__(self, connection_string, main_account):
        self._bitcoind = authproxy.AuthServiceProxy(connection_string)
        self._main_account = main_account

    def sendtoaddress(self, address, amount):
        return self._bitcoind.sendtoaddress(address, float(amount))

    def addmultisigaddress(self, n, ms):
        return self._bitcoind.addmultisigaddress(n, ms)

