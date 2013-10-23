"""Bitcoind RPC"""

import decimal
import binascii

from bitcoinrpc import authproxy

from pycoin.encoding import (is_valid_bitcoin_address, 
                             sec_to_public_pair, 
                             EncodingError)

class InvalidParameter(Exception): pass
class BitcoindError(InvalidParameter): pass
class BitcoindAuthError(BitcoindError): pass

class BitcoindConnection(object):
    """Bitcoind RPC wrapper that implements some parameter checking
    and handles Bitcoind error messages somewhat more gracefully.
    """

    def __init__(self, connection_string):
        self._bitcoind = authproxy.AuthServiceProxy(connection_string)

    def _call(self, op, *args):
        try:
            return getattr(self._bitcoind, op)(*args)
        except authproxy.JSONRPCException:
            self._wrap_jsonrpc_exception()
        except ValueError:
            self._wrap_auth_exception()

    def _wrap_jsonrpc_exception(self):
        """Extracts the bitcoind error message from the jsonrpc local scope

        Must be called from an `except` block.
        """
        import sys
        tb = sys.exc_info()[2]
        while 1:
            if not tb.tb_next:
                break
            tb = tb.tb_next
        raise BitcoindError(tb.tb_frame.f_locals["response"]["error"]["message"])

    def _wrap_auth_exception(self):
        """Wraps bitcoind's auth error response. Normally if an
        incorrect RPC username:password string is given, bitcoind just
        responds with a HTML page that JSONRPC doesn't handle at all.

        Extracts the error message from the HTML page contained in
        json's local scope.

        Must be called from an `except` block.
        """

        import sys
        tb = sys.exc_info()[2]
        while 1:
            if not tb.tb_next:
                break
            tb = tb.tb_next
        tb_file = tb.tb_frame.f_code.co_filename
        if not (tb_file.endswith("json/decoder.py") or tb_file.endswith("json/decoder.pyc")):
            # Don't know how to deal with other json libraries
            raise
        
        html = tb.tb_frame.f_locals["s"]
        
        if not html.startswith("<!DOCTYPE HTML"):
            # It's not what we know how to deal with
            raise

        header_start = html.index("<H1>")
        if header_start == -1:
            # No header, no info
            raise
        header_start += len("<H1>")
        header_end = html.index("</H1>")
        if header_end == -1:
            # Wot?
            raise
        
        raise BitcoindAuthError(html[header_start:header_end])

    def sendtoaddress(self, address, amount):
        try:
            amount = float(amount)
        except decimal.InvalidOperation:
            raise InvalidParameter(u"'%s' is not a valid number" % amount)

        try:
            return self._bitcoind.sendtoaddress(address, amount)
        except authproxy.JSONRPCException:
            self._wrap_jsonrpc_exception()
        except ValueError:
            self._wrap_auth_exception()

    def getnewaddress(self):
        return self._call("getnewaddress")

    def createrawtransaction(self, inputs, outputs):
        # TODO do some validation: inputs is a list of dicts, outputs
        # is a dict
        return self._call("createrawtransaction", inputs, outputs)

    def getrawtransaction(self, txid):
        return self._call("getrawtransaction", txid)

    def decoderawtransaction(self, rawtx):
        return self._call("decoderawtransaction", rawtx)
        
    def _is_valid_pubkey(self, k):
        try:
            sec_to_public_pair(binascii.unhexlify(k.encode("ascii")))
            return True
        except EncodingError:
            return False

    def createmultisig(self, n, ms):
        try:
            int(n)
        except ValueError:
            raise InvalidParameter(u"'%s' is not a valid integer")

        try:
            ms = list(ms)
        except TypeError:
            raise InvalidParameter(u"'%s' is not a valid sequence of public keys" % ms)

        if not all(self._is_valid_pubkey(m) for m in ms):
            raise InvalidParameter(u"The following public keys are NOT valid: %s" % ", ".join(m for m in ms if not self._is_valid_pubkey(m)))

        if n > len(ms):
            raise InvalidParameter(u"n (%s) cannot be less than the number of ms (%s)" % (n, len(ms)))

        try:
            return self._bitcoind.createmultisig(int(n), list(ms))
        except authproxy.JSONRPCException:
            self._wrap_jsonrpc_exception()
        except ValueError:
            self._wrap_auth_exception()
