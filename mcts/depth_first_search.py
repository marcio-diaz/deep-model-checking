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
from program import *


def depth_first_search(start_state, visited=None):
	state = start_state.advance_until_no_more_local_actions()
#	state.print_program_state()
	if state.is_counter_example():
#		state.print_program_state()
		print "Counter-example found :)"
		return True
	if visited is None:
		visited = set()
	visited.add(state)
	thread_states = state.pos[1]
	for action in range(len(thread_states)):
#		print action
		next_state = state.perform(action)	
		if next_state not in visited:
#			print "Not in visited."
			is_found = depth_first_search(next_state, visited)
			if is_found:
				return True
		else:
			pass
#			print "In visited."
	return False

if __name__ == "__main__":
	script, filename = argv
	f = open(filename)
	source_code = f.readlines()
	cleaned_source_code = clean(source_code)
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
	depth_first_search(state, set())
	

