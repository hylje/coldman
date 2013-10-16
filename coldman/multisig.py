"""Initial implementation of a multisig cold wallet generator."""

import sys
from binascii import hexlify

import pycoin.wallet
from pycoin.encoding import public_pair_to_sec

from coldman import conf

def main(argv):
    if len(argv) < 2:
        print "Usage:"
        print "%s <datafile> [%s]" % (argv[0], "|".join(actions))
        print "To begin, use init to create a new datafile."
        sys.exit(1)

    db_name = argv[1]

    if argv[2] == "init":
        conf.init(db_name)
        sys.exit(0)
    else:
        conf.configure(db_name)

    try:
        actions[argv[2]](*argv[3:])
    finally:
        conf.db.close()

@conf.require
def addpub(key, *remarks):
    index = get_i()
    if index != 1:
        print "It is not possible to add new public keys after some "
        print "funds have been frozen. Please create a new data file, "
        print "add (and omit) public keys to it, and migrate funds to it." 
        sys.exit(2)
        
    key = pycoin.wallet.Wallet.from_wallet_key(key)

    remark = u" ".join(remarks)
    cursor = conf.db.cursor()
    cursor.execute(
        "INSERT INTO coldman_pubkeys (key, remark) VALUES (?, ?)", (
            key.wallet_key(as_private=False), 
            remark))
    conf.db.commit()

    n = get_n()
    m = len(_get_wallets())

    if n > m:
        print "Note: %s more public keys must be added before freeze is available for use." % n-m

def genkey():
    """Generates a new deterministic private key using pycoin."""
    print "Please enter a seed that will act as the master secret."
    print "Leave empty to use a generated seed."
    secret_phrase = raw_input("Please enter the seed: ")
    random_phrase = False

    if not secret_phrase.strip():
        import os
        secret_phrase = os.urandom(512)
        random_phrase = True

    wallet = pycoin.wallet.Wallet.from_master_secret(secret_phrase)
    print "Private key"
    print wallet.wallet_key(as_private=True)
    print "-"*78
    print "Public key"
    print wallet.wallet_key(as_private=False)
    print "-"*78
    print "Save the private part in a secure location and don't tell"
    print "it to anybody."
    if not random_phrase: 
        print "You can also save the secret phrase, as"
        print "the same key can be generated from that as well."

@conf.require
def freeze(amount):
    """Freezes `amount` (decimal.Decimal) amount of funds from
    `wallet` (django_bitcoin.models.Wallet) to a new cold wallet
    identified by `ms` (pycoin.wallet.Wallet) public keys, of which
    `n` (int) are needed to withdraw.

    The `ms` are first derived into an (usually) unique index, so the
    resulting multi-sig address is fresh.

    The cold wallets can be thawed by creating an unsigned transaction
    that is then signed by at least `n` private key holders, then sent
    into the bitcoin network.
    """
    ms = _get_wallets()
    n = get_n()
    m = len(ms)

    if n > m:
        print "Need to add %s more public keys before freeze is available for use. Exiting." % n-m
        sys.exit(7)

    if m > 1:
        addr = _make_multisig_addr(ms, n)
    elif m == 1:
        addr = _make_normal_addr(ms[0])
    else:
        print "Datafile has no public keys."
        sys.exit(5)

    txid = conf.bitcoind.sendtoaddress(addr, amount)
    
    cursor = conf.db.cursor()
    cursor.execute("""
INSERT INTO coldman_txlog (i, address, txid, date_created, amount)
VALUES (?, ?, ?, datetime(), ?)
""", (get_i(), addr, txid, amount))
    conf.db.commit()

    print "Transaction ID:", txid

@conf.require
def thaw_init(i, amount):
    """Creates a transaction stub that once signed by at least `n`
    keys allows withdrawing money from a frozen multi-sig stash.

    Get the i by looking up the addr from either report_log (if
    there's a log) or report_scan (if the log is stale).

    Basically wraps bitcoind.createrawtransaction, and bundles it with
    the i
    """

    addr = _make_multisig_addr(_get_wallets(), get_n(), i=i)

    # option 1: we have the transaction logged
    cursor = conf.db.cursor()
    row_count = cursor.execute("""
SELECT txid FROM coldman_txlog WHERE i=?
""", (i,))
    if row_count:
        txid, = cursor.fetchone()
    else:
        # option 2: look it up from b.info
        # TODO binfo.unspent_outputs should be implemented
        unspent = conf.binfo.unspent_outputs(address=addr)
        # XXX normalize amounts here, b.info returns a fixed point
        # integer
        txs = [t for t in unspent["unspent_outputs"] if t["value"] > amount]
        txs.sort(key=lambda item: item["value"])
        if txs:
            txid = txs[0]["tx_hash"]
        else:
            print "Could not find spendable transactions for that i."
            sys.exit(8)

    txn = conf.bitcoind.createrawtransaction(
        [{
                "txid": txid,
                "vout": 0,
                "scriptPubkey": None, # TODO
                "redeemScript": None  # TODO
                }],
        [{addr: amount}])

    
    # https://gist.github.com/gavinandresen/3966071

@conf.require
def thaw_sign():
    """Adds the given private key's signature to the thaw transaction.
    
    Basically wraps bitcoind.signrawtransaction
    """

@conf.require
def thaw_send():
    """Sends a signed thaw transaction to the Bitcoin network.

    Basically wraps bitcoind.sendrawtransaction
    """

@conf.require
def report_scan():
    """Finds all addresses by all known permutations of `ms` and gets
    their balances from Blockchain.info.
    """    
    irange = xrange(0, get_i()+1)
    report = list(_report_addresses(irange))
    ii, addrs = zip(report)
    addr_info = conf.binfo.multiaddr(active=addrs)
    
    balances = dict((addr["address"], addr["final_balance"])
                    for addr in addr_info["addresses"])

    print "Total %s addresses:" % len(addrs)
    for i, addr in report:
        print u"%s %s %s" % (i, addr, balances[addr])

@conf.require
def report_log():
    """Prints out all logged outgone transactions."""

    cursor = conf.db.cursor()
    row_count = cursor.execute("""
SELECT i, address, date_created, txid, amount FROM coldman_txlog
""")
    print "Total %s transactions:" % row_count
    for row in cursor.fetchall():
        print " ".join(row)

actions = {"freeze": freeze, 
           "report_scan": report_scan,
           "report_log": report_log,
           "addpub": addpub, 
           "genkey": genkey,
           "init": conf.init}

@conf.require
def _report_addresses(irange):
    ms = _get_wallets()
    n = get_n()

    for i in irange:
        try:
            ms_i = [hexlify(public_pair_to_sec(m.subkey(i).public_pair)) 
                    for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            continue
        addr = conf.bitcoind.addmultisigaddress(n, ms_i)
        yield addr

@conf.require
def _make_multisig_addr(ms, n):

    i = get_i()
    i += 1
    ms_i = []
    while not ms_i:
        try:
            ms_i = [hexlify(public_pair_to_sec(m.subkey(i).public_pair))
                    for m in ms]
        except pycoin.wallet.InvalidKeyGeneratedError:
            i += 1
            
    addr = conf.bitcoind.addmultisigaddress(n, ms_i)

    save_i(i)

    return addr

@conf.require
def _make_normal_addr(wallet):
    return wallet.bitcoin_address()

@conf.require
def _get_wallets():
    cursor = conf.db.cursor()
    cursor.execute("SELECT key FROM coldman_pubkeys")
    wallet_keys = cursor.fetchall()
    return [pycoin.wallet.Wallet.from_wallet_key(key) 
            for key, in wallet_keys]

@conf.require
def get_i():
    cursor = conf.db.cursor()
    cursor.execute("SELECT value FROM coldman_settings WHERE key='index'")
    i, = cursor.fetchone()
    return int(i)

@conf.require
def save_i(i):
    cursor = conf.db.cursor()
    cursor.execute("UPDATE coldman_settings SET value=? WHERE key='index'", (unicode(i),))
    conf.db.commit()

@conf.require
def get_n():
    cursor = conf.db.cursor()
    cursor.execute("SELECT value FROM coldman_settings WHERE key='keys_minimum'")
    n, = cursor.fetchone()
    return int(n)

if __name__ == "__main__":
    main(sys.argv)
