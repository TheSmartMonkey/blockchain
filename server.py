import json
import requests
from flask import Flask, jsonify, request

from node import Node,BackgroundMiner,SignatureError,OutOfToken 


import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s %(message)s')


# Instantiate the Node
app = Flask(__name__)

node=Node()



@app.route('/mine', methods=['GET'])
def mine():
    block=node.mine()
    response = {
        'message': "New Block Forged",
        'block': block.to_dict()
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    # Check that the required fields are in the POST'ed data
    if all(k in values for k in ['transaction','signature','public_key']) \
        and all(k in values['transaction'] for k in ['sender', 'recipient', 'amount']):
        try:
            index=node.new_transaction(values)
            logger.info("transaction added:"+json.dumps(values))
            return f'Transaction will be added to Block {index}', 200
        except SignatureError:
            logger.error("Signature error in transaction "+json.dumps(values))
            return "Bad Signature",403
        except OutOfToken:
            logger.error("Not enough token for "+json.dumps(values))
            return "Not enough token",403
        except Exception as e:
            logger.error("Error "+e.__repr__()+" when creating transaction "+json.dumps(values))
            return "Invalid transaction",403
    else:
        return 'Missing values', 404

@app.route('/transactions/get/<address>')
def get_transactions(address):
    logger.info("getting transactions for address:"+address)
    def transaction_status(transaction,status):
        trdict=transaction.to_dict()
        trdict["status"]=status
        return trdict

    response = {
        'sent':[transaction_status(transaction,status) for transaction,status in node.blockchain.iter_transaction() if transaction.sender==address],
        'received':[transaction_status(transaction,status) for transaction,status in node.blockchain.iter_transaction() if transaction.recipient==address],
        'balance': node.blockchain.get_user_balance(address)
    }
    return jsonify(response), 200


@app.route('/broadcast/event', methods=['POST'])
def broadcast_event():
    values = request.get_json()

    if all(k in values for k in ['event','nodefrom', 'visited_nodes']):
        node.received_event(values['event'],values['nodefrom'],set(values['visited_nodes']))
        return 'OK', 200
    else:
        return 'Missing values', 400


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': [block.to_dict() for block in node.blockchain.chain],
        'length': len(node.blockchain.chain),
        'lastblock_hash':node.blockchain.last_block.hash()
    }
    return jsonify(response), 200

@app.route('/block/<int:block_number>', methods=['GET'])
def get_block(block_number):
    try:
        response = node.blockchain.chain[block_number].to_dict()
        return jsonify(response), 200
    except:
        return "Invalid block number",404


@app.route('/save', methods=['GET'])
def save_chain():
    node.save_chain(node.blockchain.chain)
    return "Chain saved", 200


@app.route('/nodes/add', methods=['POST'])
def add_node():
    values = request.get_json()

    newNode = values.get('node')
    if newNode is None:
        return "Error: Please supply a valid node url", 400

    nodeList=node.add_node(newNode)

    response = {
        'nodes': list(nodeList),
    }
    return jsonify(response), 200


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = node.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': node.blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': node.blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-d', '--host', default="localhost", type=str, help='host name default is localhost')
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    parser.add_argument('-r', '--register', default=None, type=str, help='server to register in')
    parser.add_argument('-M', '--mine', default="manual", type=str,choices=("nanual","auto"), help='Manual or auto run of the miner')
    args = parser.parse_args()

    node.set_node_url(f"{args.host}:{args.port}")
    node.init_blockchain()

    if args.register is not None:
        node.register_node(args.register)
    
    if args.mine == "auto":
        BackgroundMiner(node)
    
    app.run(host=args.host, port=args.port)
