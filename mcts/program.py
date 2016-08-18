from mcts.mcts import *
from mcts.tree_policies import *
from mcts.default_policies import *
from mcts.backups import *
from mcts.graph import *
from random import randint
from itertools import product, chain
from pycparser import c_parser, c_ast, parse_file, c_generator
from sys import argv
from mc import *
import copy
from clean_code import clean
from math import fabs

def tuplify(value):
    if isinstance(value, list) or isinstance(value, tuple) \
       or isinstance(value, dict):
        return tuple(tuplify(x) for x in value)
    else:
        return value

def thread_copy(t):
    tt = t[0], t[1][:], t[2].copy()
    return tt
    
def threads_copy(ts):
    res = []
    for t in ts:
        res.append(thread_copy(t))
    return res
    
class ProgramAction(object):
    def __init__(self, move):
        self.move = move

    def __eq__(self, other):
        return (self.move == other)

    def __hash__(self):
        return self.move

    def __str__(self):
        return self.move


class ProgramState(object):
    def __init__(self, pos):
        # we assume @pos is a list [global_vars, threads, ast, ce]  
        self.pos = pos
        gv, ts, ast, ce = pos
        # thus we have one action for each thread
        ts = [t for t in ts if t != None]
        self.actions = [idx for idx in range(len(ts))]
        


    def perform(self, action):
        # @ce is a boolean that indicate if the state
        # is a counterexample.
        gv, ts, ast, ce = self.pos
#        print("in threads {}\n".format(ts))
        ts2 = threads_copy(ts)
        gv2, t, ce = process_line(gv.copy(), action, ts2, ast)
        if t != None and ce == 0:
            ts2[action] = thread_copy(t)
#        print("out threads {}\n".format(ts2))           
        return ProgramState((gv2, ts2, ast, ce))

    def reward(self, parent, action):
        gv, ts, ast, ce = self.pos
#        s = int(gv['sum'])
        i = int(gv['i'])
        j = int(gv['j'])        
        if ce == 1:
 #           print("reward 10")
            return 1
        elif ce == 0:
            #print("reward 0")
#            if s >= 1:
#                return -1
            return 0
        else:
            assert(ce == -1)
#            return 0
            #print("reward -10")            
#            return (-(46368-i)-(46368-j))*100
            return max(j, i)/21.0

    def is_terminal(self):
        if self.pos[3] != 0:
#            print("terminal")
            return True
        else:
            return False


    def __eq__(self, other):
        return (self.pos == other.pos)

    def __hash__(self):
        return hash(tuplify(self.pos))


if __name__ == "__main__":
    script, filename = argv
    # read source code
    f = open(filename)
    source_code = f.readlines()
    cleaned_source_code = clean(source_code)
    # parse clean code
    parser = c_parser.CParser()
    ast = parser.parse(cleaned_source_code)
    gv = get_global_state(ast)
    ts = [("main", [get_func_node(ast, "main")], {})]
#    k_step_rollout = RandomKStepRollOut(10000)
    mcts = MCTS(tree_policy=UCB1(c=10.41),
                default_policy=random_k_terminal_roll_out,
                backup=monte_carlo)

    state = ProgramState((gv, ts, ast, False))
    while not state.is_terminal():
        root = StateNode(None, state)
        print("{} {}".format(state.pos[0], \
#                                  [t[2] for t in state.pos[1]],
                                state.pos[1]))
#                                state.pos[1][0][1][0]))
        best_action, reward = mcts(root, 10000)
        print("\nreward = {}".format(reward))
#        if reward > 0.9:
#            print("Counterexample found :)")
#            print(state.pos[0])
#            break
        state = state.perform(best_action)
#        if state in root.children:
#            root = root.children[state]
#            root.parent = None

