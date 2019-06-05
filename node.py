from uuid import uuid4
import requests
import json
from random import sample

import logging
logger = logging.getLogger(__name__)

# number of node that each node send the message to in the P2P network
ADJENCENT_NODES = 3

from block import Blockchain,Transaction,SignedTransaction,transaction_from_dict,block_from_dict

class SignatureError(Exception):
    """exceptions in case of bad signature"""
    pass

class Node(object):
    """
    Implement a blochain node
    """
    def __init__(self):
        self.node_identifier = str(uuid4()).replace('-', '')
        self.nodeUrl=None
        self.nodeList = set()
        self.blockchain = Blockchain()

    def set_node_url(self,nodeUrl):
        self.nodeUrl = nodeUrl
        self.nodeList.add(nodeUrl)

    def register_node(self,registerNodeUrl):
        logger.info(f'Registering node {self.nodeUrl} into {registerNodeUrl}')
        response = requests.post(f"http://{registerNodeUrl}/nodes/add",
                        headers={"Content-Type": "application/json"}, 
                        data=json.dumps({"node":self.nodeUrl}))
        values = response.json()
        self.nodeList = set(values['nodes'])
        logger.info("Connected to nodes:"+",".join(self.nodeList))
        # simple to initialise the blockchain
        self.blockchain.chain = []
        self.resolve_conflicts()

    def add_node(self,newNodeUrl):
        logger.info(f'Adding node {newNodeUrl}')
        if newNodeUrl not in self.nodeList:
            self.nodeList.add(newNodeUrl)
            self.broadcast_event({"type":"new_node","nodeUrl":newNodeUrl},set([newNodeUrl]))
        return self.nodeList

    def add_nodes(self,addNodeList):
        self.nodeList = self.nodeList.union(addNodeList)

    def parse_transaction_values(self,values):
        trvalues = values['transaction']
        transaction = transaction_from_dict(trvalues)
        signedTransaction = SignedTransaction(transaction,values['signature'],values['public_key'])
        return signedTransaction

    def new_transaction(self,values):
        signedTransaction = self.parse_transaction_values(values)
        if signedTransaction.is_valid():
            index = self.blockchain.new_transaction(signedTransaction.transaction)
            logger.info("New transaction added coming client")
            self.broadcast_event({"type":"new_transaction","transaction":values},set())
            return index
        else:
            raise SignatureError

    def broadcast_event(self,event,visitedNodes):
        visitedNodes.add(self.nodeUrl)
        targetedNodes = self.nodeList.difference(visitedNodes)
        if len(targetedNodes) > ADJENCENT_NODES:
            # if to many node we sample to a sublist and let the other nodes do the work
            targetedNodes = sample(targetedNodes,ADJENCENT_NODES)
        newVisitedNodes = visitedNodes.union(targetedNodes)
        if len(targetedNodes)>0:
            message = json.dumps({"event":event,"nodefrom":self.nodeUrl,"visited_nodes":list(newVisitedNodes)})
            logger.debug("broacasting message"+message+" to:"+",".join(targetedNodes))
            # we target only a subset of node expecting the other to broadcast the message to their neighbours
            for node in targetedNodes:
                requests.post(f"http://{node}/broadcast/event",
                                headers={"Content-Type": "application/json"}, 
                                data=message)

    def received_event(self,event,nodefrom,visitedNodes):
        logger.debug('event received '+ json.dumps(event))
        if event["type"] == "new_node":
            newUrl = event["nodeUrl"]
            self.nodeList.add(newUrl)
            logger.info(f"node {newUrl} added")
            logger.debug(f"all nodes "+",".join(self.nodeList))
        elif event["type"]=="new_transaction":
            # we should validate if the transaction is valid to avoid forged transactions
            values = event["transaction"]
            signedTransaction = self.parse_transaction_values(values)
            if signedTransaction.is_valid():
                index = self.blockchain.new_transaction(signedTransaction.transaction)
                logger.info("New transaction added coming from node:%s to block %d"%(nodefrom,index))
            else:
                logger.error("Received an invalid transaction")
        elif event["type"] == "new_block":
            # we should validate if the block is valid to avoid forged block
            block = block_from_dict(event["block"])
            self.blockchain.add_block(block)

        visitedNodes.add(self.nodeUrl)
        self.broadcast_event(event,visitedNodes)
    
    def mine(self):
        # We run the proof of work algorithm to get the next proof...
        proof = self.blockchain.proof_of_work()

        # We must receive a reward for finding the proof.
        # The sender is "0" to signify that this node has mined a new coin.
        #self.blockchain.new_transaction(
        #    Transaction(sender="0",recipient=self.node_identifier,amount=1)
        #)

        # Forge the new Block by adding it to the chain
        previous_hash = self.blockchain.last_block.hash()
        block = self.blockchain.new_block(proof,previous_hash)
        logger.info(f"mined block {block.index}")
        self.broadcast_event({"type":"new_block","block":block.to_dict()},set())
        return block

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: True if our chain was replaced, False if not
        """

        logger.info("Resolving conflicts")
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.blockchain.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in self.nodeList:
            if node != self.nodeUrl:
                response = requests.get(f'http://{node}/chain')

                if response.status_code == 200:
                    length = response.json()['length']
                    chain_dict = response.json()['chain']
                    chain = [block_from_dict(json_block) for json_block in chain_dict]
                    print(chain)
                    # Check if the length is longer and the chain is valid
                    if not self.blockchain.valid_chain(chain):
                        logger.debug("invalid chain received")
                        continue
                    if length > max_length:
                        max_length = length
                        new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            logger.info("New chain loaded")
            print(new_chain)
            self.blockchain.chain = new_chain
            return True

        return False


