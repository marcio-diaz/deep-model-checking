from __future__ import division
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
from itertools import chain

def compute_reward(reward_functions, global_variables):
    rewards = []
    for rf, var_name in reward_functions:
        r = rf(global_variables[var_name])
        rewards.append(r)
    return rewards
    

def to_reward_function(binary_operator):
    assert isinstance(binary_operator, c_ast.BinaryOp)
    big_num = 1000.0
    if binary_operator.op == "!=":
        var_name = binary_operator.left.name
        value = float(binary_operator.right.value)
        func = lambda x: abs(big_num - float(x)) / big_num
        return (func, var_name),
    if binary_operator.op == "&&":
        func = to_reward_function(binary_operator.left)
        func += to_reward_function(binary_operator.right)
        return func
    if binary_operator.op == "<":
        var_name = binary_operator.left.name
        value = float(binary_operator.right.value)
        func = lambda x: 1.0 - (value - float(x)) / value
        return (func, var_name),
    assert False, "Binary operator {} not recognized.".format(binary_operator.op)
    

def get_reward_functions(assert_nodes):
    reward_functions = tuple()
    for node in assert_nodes:
        rf = to_reward_function(node.args.exprs[0])
        reward_functions += rf
    return reward_functions

def get_assert_nodes(abstract_syntax_tree):
    assert_nodes = []
    for node in abstract_syntax_tree:
        if isinstance(node, c_ast.FuncDef):
            instructions = node.body.block_items[:]
            for inst in instructions:
                assert_nodes.extend(get_assert_nodes([inst]))
        elif isinstance(node, c_ast.FuncCall):
            function_name = node.name.name
            if function_name == "assert":
                assert_nodes.append(node)
    return assert_nodes

def tuplify(value):
    if isinstance(value, list) or isinstance(value, tuple) \
       or isinstance(value, dict):
        return tuple(tuplify(x) for x in value)
    else:
        return value

def thread_copy(t):
    frames_copy = []
    for frame in t[2]:
        frame_copy = (copy.deepcopy(frame[0]), copy.deepcopy(frame[1]))
        frames_copy.append(frame_copy)
    tt = t[0], t[1][:], frames_copy
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
            is_counter_example_found, is_assert_found, reward_functions = pos
        thread_states = [t for t in thread_states if t != None]
        # We have one action for each thread.
        self.actions = [a for a in range(len(thread_states))]


    def advance_until_no_more_local_actions(self):
        """ Execute as many *local* thread instructions as it can. 
        It return once all threads need to execute a instruction 
        that use global state.
        """
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found, reward_functions = self.pos
        simulate = True # Do not execute global instructions.
        thread_index = 0
        while thread_index < len(thread_states) and not is_counter_example_found:
            is_global = False
            is_blocked = False
            while not is_global and not is_counter_example_found \
                  and not is_blocked:
                if thread_index >= len(thread_states):
                    break
                global_variables, thread_states, is_counter_example_found, \
                    is_global, is_assert_found, is_blocked = \
                                                process_line(global_variables,
                                                             thread_index,
                                                             thread_states, 
                                                             abstract_syntax_tree,
                                                             simulate)
            thread_index += 1
        return ProgramState((global_variables, thread_states,
                             abstract_syntax_tree, is_counter_example_found,
                             is_assert_found, reward_functions))


    def perform(self, action):
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found, reward_functions = self.pos
        assert action < len(thread_states), "There is no thread corresponding" \
            " to action {}".format(action)
        thread_states_copy = threads_copy(thread_states)
        global_variables_copy = copy.deepcopy(global_variables)
        simulate = False
        global_variables_copy, thread_states_copy, is_counter_example_found, \
            is_global, is_assert_found, is_blocked = \
                                        process_line(global_variables_copy,
                                                     action, thread_states_copy,
                                                      abstract_syntax_tree, simulate)
        return ProgramState((global_variables_copy, thread_states_copy,
                             abstract_syntax_tree, is_counter_example_found,
                             is_assert_found, reward_functions))

    
    def reward(self, parent, action):
        global_variables, thread_states, abstract_syntax_tree, \
            is_counter_example_found, is_assert_found, reward_functions = self.pos
#        s = int(global_variables['sum']) # for sigma
#        i = int(global_variables['i']) # for fibonacci
#        j = int(global_variables['j']) # for fibonacci
#        top = int(global_variables['top']) # for stack

        if is_assert_found:
            rewards = compute_reward(reward_functions, global_variables)
#            print rewards
            return max(rewards)
#            return max(j, i)/701408733.0 # for fibonacci
#            return -(1.0/14.0) * s + 15.0/14.0 # for sigma
#            return (800.0-top)/800.0 # for stack        
        else:
            return 0.0

    def is_terminal(self):
        return (len(self.pos[1]) == 0)
#        return self.pos[4]

    def is_counter_example(self):
	return self.pos[3]

    def print_program_state(self):
	print "{}\n{}\n{}".format(self.pos[-1], self.pos[1], self.pos[4])

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

    # We get the reward function.
    assert_nodes = get_assert_nodes(abstract_syntax_tree.ext)
    reward_functions = get_reward_functions(assert_nodes)

    # Create the initial state of the program.
    global_variables = get_global_state(abstract_syntax_tree)
    thread_states = [("main", [get_function_node(abstract_syntax_tree, "main")], [])]
    counter_example_found = False
    is_assert_found = False
    state = ProgramState((global_variables, thread_states, \
                          abstract_syntax_tree, counter_example_found,
                          is_assert_found, reward_functions))

    # Instantiate Monte Carlo Tree Search algorithm.
    mcts = MCTS(tree_policy=UCB1(c=1.41),
                default_policy=random_k_terminal_roll_out,
                backup=monte_carlo)

    # Execute the program until termination.
    while not state.is_terminal() and not state.is_counter_example():
        if DEBUG:
            print "#"*10 + " Before executing all locals  " + "#"*10
        state = state.advance_until_no_more_local_actions()
        if DEBUG:
            print "#"*10 + " After executing all locals  " + "#"*10
        if state.is_terminal() or state.is_counter_example():
            break        
        root = StateNode(None, state)
        print("{}\n {}\n".format("*"*80, state.pos[0]))
        for thread in state.pos[1]:
            print "{} {} \n{}\n".format(thread[0], thread[1], thread[2])
	print("\n{} {} \n{}".format(state.pos[3], state.pos[4], "*"*80))

        number_of_iterations = 400 # for fibonacci
#        number_of_iterations = 30 # for sigma
#        number_of_iterations = 1 # stack
        best_action, reward = mcts(root, number_of_iterations)
        print("\nBest action = {}, Reward = {}.".format(best_action, reward))
        if DEBUG:
            print "#"*10 + " Before performing action  " + "#"*10        
        state = state.perform(best_action)
        if DEBUG:
            print "#"*10 + " After performing action  " + "#"*10                

    print("{} {} {} {}".format(state.pos[0], state.pos[1], 
			       state.pos[3], state.pos[4]))

    if state.is_counter_example():
        print "\nCounter-example found :)"
    else:
        print "\nCounter-example NOT found :("    
