from .utils import *

errors = 0

def trans_test(fn):
    """ Immediately runs a test that requires a blockchain, and a transaction with private key in that blockchain. """

    def wrapper():
        gen_chain = Blockchain([GENESIS_BLOCK])
        assert gen_chain.verify_all()
        key = Signing.generate_private_key()
        reward_trans = Transaction([], [TransactionTarget(key, gen_chain.compute_blockreward(gen_chain.head))])
        chain = extend_blockchain(gen_chain, [reward_trans])
        fn(chain, reward_trans)
    return wrapper

@trans_test
def test_double_spend1(chain, reward_trans):
    trans1 = new_trans(reward_trans)
    chain = extend_blockchain(chain, [trans1])

    # spending the coin in reward_trans again must fail:
    extend_blockchain(chain, [trans1], verify_res=False)

    # spending the output of trans1 must work:
    assert chain.is_coin_still_valid(trans_as_input(trans1))

@trans_test
def test_double_spend2(chain, reward_trans):
    trans1 = new_trans(reward_trans)
    trans2 = new_trans(reward_trans)
    extend_blockchain(chain, [trans1, trans2], verify_res=False)

@trans_test
def test_double_spend3(chain, reward_trans):
    trans1 = Transaction([trans_as_input(reward_trans), trans_as_input(reward_trans)], [])
    key = reward_trans.targets[0].recipient_pk
    trans1.sign([key, key])
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_create_money1(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    # create a transaction where the receiver gets 1 more coin than the sender puts in
    target = TransactionTarget(key, reward_trans.targets[0].amount + 1)
    trans1 = Transaction([trans_as_input(reward_trans)], [target])
    trans1.sign([key])
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_create_money2(chain, reward_trans):
    # create a transaction where we create money by sending a negative amount N to someone
    # and the inputs + N to us
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, -10)
    target2 = TransactionTarget(key, reward_trans.targets[0].amount + 10)
    trans1 = Transaction([trans_as_input(reward_trans)], [target1, target2])
    trans1.sign([key])
    extend_blockchain(chain, [trans1], verify_res=False)
