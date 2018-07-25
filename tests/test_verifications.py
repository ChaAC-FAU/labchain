from tests.utils import *

def block_test(proof_of_work_res=True):
    """ Immediately runs a test that requires a blockchain. """

    def decorator(fn):
        def wrapper():
            orig_proof = src.proof_of_work.verify_proof_of_work
            src.proof_of_work.verify_proof_of_work = lambda b: proof_of_work_res
            src.block.verify_proof_of_work = src.proof_of_work.verify_proof_of_work

            chain = Blockchain()

            try:
                fn(chain)
            finally:
                src.block.verify_proof_of_work = orig_proof
                src.proof_of_work.verify_proof_of_work = orig_proof
        return wrapper
    return decorator

def trans_test(fn):
    """ Immediately runs a test that requires a blockchain, and a transaction with private key in that blockchain. """

    @block_test()
    def wrapper(gen_chain):
        key = Key.generate_private_key()
        reward_trans = Transaction([], [TransactionTarget(key, gen_chain.compute_blockreward_next_block())],datetime.now())
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
    assert trans_as_input(trans1) in chain.unspent_coins

@trans_test
def test_double_spend2(chain, reward_trans):
    trans1 = new_trans(reward_trans)
    trans2 = new_trans(reward_trans)
    extend_blockchain(chain, [trans1, trans2], verify_res=False)

@trans_test
def test_double_spend3(chain, reward_trans):
    trans1 = Transaction([trans_as_input(reward_trans), trans_as_input(reward_trans)], [], datetime.now())
    key = reward_trans.targets[0].recipient_pk
    trans1.sign([key, key])
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_create_money1(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    # create a transaction where the receiver gets 1 more coin than the sender puts in
    target = TransactionTarget(key, reward_trans.targets[0].amount + 1)
    trans1 = Transaction([trans_as_input(reward_trans)], [target], datetime.now())
    trans1.sign([key])
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_create_money2(chain, reward_trans):
    # create a transaction where we create money by sending a negative amount N to someone
    # and the inputs + N to us
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, -10)
    target2 = TransactionTarget(key, reward_trans.targets[0].amount + 10)
    trans1 = Transaction([trans_as_input(reward_trans)], [target1, target2],datetime.now())
    trans1.sign([key])
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_dupl_block_reward(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, 1)
    trans1 = Transaction([], [target1], datetime.now(), iv=b"1")
    trans2 = Transaction([], [target1], datetime.now(), iv=b"2")
    extend_blockchain(chain, [trans1, trans2], verify_res=False)

@trans_test
def test_negative_block_reward(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, -1)
    trans1 = Transaction([], [target1],datetime.now(), iv=b"1")
    extend_blockchain(chain, [trans1], verify_res=False)

@trans_test
def test_zero_block_reward(chain, reward_trans):
    extend_blockchain(chain, [], verify_res=True)

@trans_test
def test_too_large_block_reward(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, chain.compute_blockreward_next_block() + 1)
    trans1 = Transaction([], [target1], datetime.now(), iv=b"1")
    extend_blockchain(chain, [trans1], verify_res=False)

    trans2 = new_trans(reward_trans, fee=1)
    target2 = TransactionTarget(key, chain.compute_blockreward_next_block() + 2)
    trans3 = Transaction([], [target2], datetime.now(), iv=b"2")
    extend_blockchain(chain, [trans2, trans3], verify_res=False)

@trans_test
def test_max_block_reward(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, chain.compute_blockreward_next_block())
    trans1 = Transaction([], [target1], datetime.now(), iv=b"1")
    extend_blockchain(chain, [trans1], verify_res=True)

    trans2 = new_trans(reward_trans, fee=1)
    target2 = TransactionTarget(key, chain.compute_blockreward_next_block() + 1)
    trans3 = Transaction([], [target2], datetime.now(), iv=b"2")
    extend_blockchain(chain, [trans2, trans3], verify_res=True)

@trans_test
def test_spend_too_much(chain, reward_trans):
    trans = new_trans(reward_trans, fee=-1)
    assert trans.targets[0].amount == reward_trans.targets[0].amount + 1
    extend_blockchain(chain, [trans], verify_res=False)

@trans_test
def test_spend_unknown_coin(chain, reward_trans):
    key = reward_trans.targets[0].recipient_pk
    inp1 = TransactionInput(reward_trans.get_hash(), len(reward_trans.targets))
    trans1 = Transaction([inp1], [], datetime.now(),)
    trans1.sign([key])
    extend_blockchain(chain, [trans1], verify_res=False)

    inp2 = TransactionInput(b"invalid", 0)
    trans2 = Transaction([inp2], [], datetime.now(),)
    trans2.sign([key])
    extend_blockchain(chain, [trans2], verify_res=False)

@trans_test
def test_send_zero(chain, reward_trans):
    trans = new_trans(reward_trans, fee=reward_trans.targets[0].amount)
    assert trans.targets[0].amount == 0
    extend_blockchain(chain, [trans], verify_res=False)

@trans_test
def test_invalid_signature(chain, reward_trans):
    trans1 = new_trans(reward_trans, fee=0)
    trans2 = new_trans(reward_trans, fee=1)
    trans1.signatures, trans2.signatures = trans2.signatures, trans1.signatures
    extend_blockchain(chain, [trans1], verify_res=False)
    extend_blockchain(chain, [trans2], verify_res=False)

    trans3 = Transaction(trans1.inputs, trans1.targets, datetime.now(), signatures=trans1.signatures+trans2.signatures)
    extend_blockchain(chain, [trans3], verify_res=False)

    trans4 = Transaction(trans1.inputs, trans1.targets, datetime.now(), signatures=[])
    extend_blockchain(chain, [trans4], verify_res=False)

    # too few signatures:
    key = reward_trans.targets[0].recipient_pk
    target1 = TransactionTarget(key, 1)
    target2 = TransactionTarget(key, 1)
    trans5 = Transaction(trans1.inputs, [target1, target2],datetime.now())
    trans5.sign([key])
    extend_blockchain(chain, [trans5], verify_res=True)
    input1 = TransactionInput(trans5.get_hash(), 0)
    input2 = TransactionInput(trans5.get_hash(), 1)
    trans6 = Transaction([input1, input2], [], datetime.now())
    trans6.sign([key, key])
    trans6.signatures.pop()
    extend_blockchain(chain, [trans6], verify_res=False)



@block_test(proof_of_work_res=False)
def test_invalid_proof_of_work(chain):
    block = Block.create(chain, [])
    assert chain.try_append(block) is None

@block_test()
def test_invalid_prev_hash(chain):
    block = create_block(chain, prev_block_hash="0001020304")
    assert chain.try_append(block) is None

@block_test()
def test_invalid_merkle_root_hash(chain):
    block = create_block(chain, merkle_root_hash="0001020304")
    assert chain.try_append(block) is None

@block_test()
def test_monotonic_time(chain):
    block = create_block(chain, time="1900-01-01T00:00:00.000000 UTC")
    assert chain.try_append(block) is None

@block_test()
def test_future_time(chain):
    block = create_block(chain, time="2900-01-01T00:00:00.000000 UTC")
    assert chain.try_append(block) is None

@block_test()
def test_invalid_height(chain):
    block = create_block(chain, height=-1)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height ** 42)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height ** 42)
    assert chain.try_append(block) is None

@block_test()
def test_invalid_difficulty(chain):
    block = create_block(chain, difficulty=-1)
    assert chain.try_append(block) is None
    block = create_block(chain, difficulty=chain.head.difficulty + 1)
    assert chain.try_append(block) is None
    block = create_block(chain, difficulty=chain.head.difficulty - 1)
    assert chain.try_append(block) is None
    block = create_block(chain, difficulty=chain.head.difficulty ** 42)
    assert chain.try_append(block) is None

@block_test()
def test_invalid_height_difficulty(chain):
    block = create_block(chain, height=chain.head.height - 1, difficulty=-1)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height, difficulty=0)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height + 1, difficulty=1)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height * 42, difficulty=chain.head.height * 41)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height + chain.head.difficulty + 1,
                                difficulty=chain.head.difficulty + 1)
    assert chain.try_append(block) is None
    block = create_block(chain, height=chain.head.height + chain.head.difficulty - 1,
                                difficulty=chain.head.difficulty - 1)
    assert chain.try_append(block) is None
