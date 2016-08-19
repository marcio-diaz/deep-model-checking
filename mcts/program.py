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
        self.pos = pos
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found = pos
        thread_states = [t for t in thread_states if t != None]
        # We have one action for each thread.
        self.actions = [a for a in range(len(thread_states))]


    def advance_until_no_more_local_actions(self):
        """ Execute as many *local* thread instructions as it can. 
        It return once all threads need to execute a instruction 
        that use global state.
        """
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found = self.pos
        simulate = True # Do not execute global instructions.
        thread_index = 0
        while thread_index < len(thread_states):
            is_global = False
            while not is_global:
                if thread_index >= len(thread_states):
                    break
                global_variables, thread_states, is_counter_example_found, \
                    is_global, is_assert_found = process_line(global_variables,
                                                              thread_index,
                                                              thread_states, 
                                                              abstract_syntax_tree,
                                                              simulate)
            thread_index += 1
        return ProgramState((global_variables, thread_states,
                             abstract_syntax_tree, is_counter_example_found,
                             is_assert_found))


    def perform(self, action):
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found = self.pos
        assert action < len(thread_states), "There is no thread corresponding" \
            " to action {}".format(action)
        thread_states_copy = threads_copy(thread_states)
        global_variables_copy = global_variables.copy()
        simulate = False
        global_variables_copy, thread_states_copy, is_counter_example_found, \
            is_global, is_assert_found = process_line(global_variables_copy,
                                                      action, thread_states_copy,
                                                      abstract_syntax_tree, simulate)
        return ProgramState((global_variables_copy, thread_states_copy,
                             abstract_syntax_tree, is_counter_example_found,
                             is_assert_found))

    
    def reward(self, parent, action):
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found = self.pos
        s = int(global_variables['sum']) # for sigma
#        i = int(global_variables['i']) # for fibonacci
#        j = int(global_variables['j']) # for fibonacci      
        if is_assert_found:
#            return max(j, i)/46368.0 # for fibonacci
            return -(1.0/14.0) * s + 15.0/14.0 # for sigma
        else:
            return 0.0

    def is_terminal(self):
        return self.pos[4]

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
    is_assert_found = False
    state = ProgramState((global_variables, thread_states, \
                          abstract_syntax_tree, counter_example_found,
                          is_assert_found))

    # Instantiate Monte Carlo Tree Search algorithm.
    mcts = MCTS(tree_policy=UCB1(c=1.41),
                default_policy=random_k_terminal_roll_out,
                backup=monte_carlo)

    # Execute the program until termination.
    while not state.is_terminal():
        state = state.advance_until_no_more_local_actions()
        root = StateNode(None, state)
        print("{} {}".format(state.pos[0], state.pos[1]))
        if state.is_terminal():
            break

#        number_of_iterations = 2500 # for fibonacci
        number_of_iterations = 30 # for sigma
        best_action, reward = mcts(root, number_of_iterations)
        print("\nBest action = {}, Reward = {}.".format(best_action, reward))
        state = state.perform(best_action)

    if state.pos[3]:
        print "\nCounter-example found :)"
    else:
        print "\nCounter-example NOT found :("    
