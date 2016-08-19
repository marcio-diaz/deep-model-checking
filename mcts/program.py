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


    def advance_until_no_more_local_actions(self):
        gv2, ts2, ast, ce = self.pos        
        i = 0
        while i < len(ts2):
#            print i
            ug = False
            while not ug:
                gv2, t, ce, ug = process_line(gv2, i, ts2, ast, True)
                if t != None and ce == 0:
                    ts2[i] = thread_copy(t)
                else:
                    break
            i += 1

        return ProgramState((gv2, ts2, ast, ce))

    def perform(self, action):
        # @ce is a boolean that indicate if the state
        # is a counterexample.
        gv, ts, ast, ce = self.pos
#        print("in threads {}\n".format(ts))
        ts2 = threads_copy(ts)
        gv2 = gv.copy()
        ug = False

        while not ug:
            gv2, t, ce, ug = process_line(gv2, action, ts2, ast, False)
            if t != None and ce == 0:
                ts2[action] = thread_copy(t)
            else:
                break
            
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
            return max(j, i)/46368.0

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

    # Read source code.
    f = open(filename)
    source_code = f.readlines()

    # We remove some directives not supported by pycparser
    # and change 'for' loops to 'while' loops.
    cleaned_source_code = clean(source_code)

    # Parse clean code.
    parser = c_parser.CParser()
    abstract_syntax_tree = parser.parse(cleaned_source_code)

    # Create the initial state of the program.
    global_variables = get_global_state(abstract_syntax_tree)
    thread_states = [("main", [get_function_node(abstract_syntax_tree, "main")], {})]
    counter_example_found = False
    state = ProgramState((global_variables, thread_states, \
                          abstract_syntax_tree, counter_example_found))

    # Instantiate Monte Carlo Tree Search algorithm.
    mcts = MCTS(tree_policy=UCB1(c=1.41),
                default_policy=random_k_terminal_roll_out,
                backup=monte_carlo)

    # Execute the program until termination.
    while not state.is_terminal():
        state = state.advance_until_no_more_local_actions()
        root = StateNode(None, state)
        print("{} {}".format(state.pos[0], state.pos[1]))
        number_of_iterations = 2500
        best_action, reward = mcts(root, number_of_iterations)
        print("\nBest action = {}, Reward = {}.".format(best_action, reward))
        state = state.perform(best_action)

    print("{} {}".format(state.pos[0], state.pos[1]))
