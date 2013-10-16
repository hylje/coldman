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

    # TODO dump an unsigned transaction instead?
    txid = conf.bitcoind.sendtoaddress(addr, amount)
    
    cursor = conf.db.cursor()
    cursor.execute("""
INSERT INTO coldman_txlog (i, address, txid, date_created, amount)
VALUES (?, ?, ?, datetime(), ?)
""", (get_i(), addr, txid, amount))
    conf.db.commit()

    print txid

@conf.require
def thaw(i, output_addr=None):
    """Creates a transaction stub that once signed by at least `n`
    keys allows withdrawing money from a frozen multi-sig stash.

    Get the `i` by looking up the addr from either report_log (if
    there's a log) or report_scan (if the log is stale).

    If no `output_addr` is given, the transaction will be made to the
    hot wallet.

    There will be a 0.0001 BTC fee automatically.

    Basically wraps bitcoind.createrawtransaction.

    Sign the resulting transaction with e.g. Electrum >=1.9

    Also see:
    https://gist.github.com/gavinandresen/3966071
    """
    if output_addr is None:
        output_addr = conf.bitcoind.getnewaddress()

    cursor = conf.db.cursor()
    row_count = cursor.execute("""
SELECT txid, amount FROM coldman_txlog WHERE i=?
""", (i,))
    if not row_count:
        print "Unknown index. The internal transaction log might be stale."
        sys.exit(8)
    
    txid, amount = cursor.fetchone()
    
    # the txn could require redeemScript and scriptPubKey if the
    # original txid is not in the network
    # but usually not

    fee = 0.0001

    if amount - fee < 0:
        amount_with_fee = amount
    else:
        amount_with_fee = amount - fee
    
    txn = conf.bitcoind.createrawtransaction(
        [{"txid": txid,
          "vout": 0,
          }],
        {output_addr: max(0, amount_with_fee)})

    print txn

@conf.require
def report():
    """Prints out all logged, unspent outgone transactions. We'll
    check the transactions' spentness on Blockchain.info, and mark
    those that are spent. For our purposes, "spent" means the address
    has an outgoing transaction.

    The data to recreate the log from scratch does exist in the
    blockchain, but it's a lot of work to do that. It involves looping
    every possible public key set up to a known value, and then
    looking up whether those public key sets have a multisig address
    with unspent bitcoins.
    """

    cursor = conf.db.cursor()
    cursor.execute("""
SELECT address 
FROM coldman_txlog 
WHERE spent=0
""")

    addrs = [a for a, in cursor.fetchall()]
    if addrs:
        info = conf.binfo.multiaddr(addrs)
    else:
        print "No known (potentially) unspent transactions."

    spent_addrs = set()
    for addr in info["addresses"]:
        # addresses with less than minimum tx are as good as spent
        if addr["total_received"] < 5500:
            spent_addrs.add(addr["address"])

    cursor.execute("""
UPDATE coldman_txlog SET spent=1 WHERE address IN (%s)
""" % (",".join("?"*len(spent_addrs))), list(spent_addrs))

    conf.db.commit()

    cursor.execute("""
SELECT i, address, date_created, amount 
FROM coldman_txlog 
WHERE spent=0
""")

    print "i addr date amount"
    for row in cursor.fetchall():
        print "{} {} {} {:.8f}".format(*row)

actions = {"freeze": freeze, 
           "thaw": thaw,
           "report": report,
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
        info = conf.bitcoind.createmultisig(n, ms_i)
        yield i, info["address"]

@conf.require
def _get_multisig_addr(ms, n, i):
    ms_i = [hexlify(public_pair_to_sec(m.subkey(i).public_pair))
            for m in ms]    
    info = conf.bitcoind.createmultisig(n, ms_i)
    return info
    
@conf.require
def _make_multisig_addr(ms, n):

    i = get_i()
    i += 1
    ms_i = []
    while not ms_i:
        try:
            info = _get_multisig_addr(ms, n, i)
        except pycoin.wallet.InvalidKeyGeneratedError:
            i += 1

    save_i(i)

    return info

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
