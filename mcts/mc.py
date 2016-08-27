from random import randint, randrange
from itertools import product, chain
from pycparser import c_parser, c_ast, parse_file, c_generator
from sys import argv


def get_variable_value(global_variables, local_variables, variable_name):
    """ Given a name of a variable it returns its value.
    """
    is_global = False
    if variable_name in local_variables.keys():
        return local_variables[variable_name], is_global
    if variable_name in global_variables.keys():
        is_global = True
        return global_variables[variable_name], is_global
    assert False, "There is no variable with {} name.".format(variable_name)

    
def set_variable_value(global_variables, local_variables, variable_name, value):
    """ Given a name of a variable and a value, it sets the variable
    to that value.
    """
    if variable_name in local_variables.keys():
        local_variables[variable_name] = value
        return global_variables, local_variables
    if variable_name in global_variables.keys():
        global_variables[variable_name] = value
        return global_variables, local_variables
    
    assert False, "There is no variable with {} name.".format(variable_name)

    
def get_value(expression, global_variables, local_variables):
    """ Given a constant, variable or array expression, 
    it returns its value. It also indicates if the returned value comes
    from reading a global variable or not.
    """
    is_from_global_variable = False
    if isinstance(expression, c_ast.ID):
        return get_variable_value(global_variables, local_variables, expression.name)
    elif isinstance(expression, c_ast.Constant):
        return expression.value, is_from_global_variable
    elif isinstance(expression, c_ast.ArrayRef):
        idx_var_name, is_idx_global = get_variable_value(global_variables, 
                                                         local_variables, 
							 expression.subscript.name)
        var_name =  "{}{}".format(expression.name.name, idx_var_name)
        value, is_var_global = get_variable_value(global_variables, 
                                                  local_variables, var_name)
        is_from_global_variable = (is_idx_global or is_var_global)
        return value, is_from_global_variable
    elif isinstance(expression, c_ast.BinaryOp):
        assert expression.left.name.name == "__VERIFIER_nondet_uint"
        assert expression.op == "%"
        num = randrange(0, 1000000)
        mod, _ = get_value(expression.right, global_variables, local_variables)
        return num % int(mod), False
    assert False, "The expression parameter is {}, not a constant, " \
        "variable or array.".format(expression)

    
def get_variable(expression, global_variables, local_variables):
    """ Given an array or a variable, it returns its name.
    """
    if isinstance(expression, c_ast.ArrayRef):
        value, is_global = get_variable_value(global_variables, local_variables, 
						  expression.subscript.name)
	return "{}{}".format(expression.name.name, value), is_global
    if isinstance(expression, c_ast.ID):
        return expression.name, False
    if isinstance(expression, c_ast.UnaryOp):
        return expression.expr.name, True

    assert False, "The expression parameter is not a variable or an array."

    
def evaluate_boolean_expression(expression, global_variables, local_variables):
    """ Given a boolean expression it returns its value. TODO: make it work
    for literals. Also, it only support integers inside the expression. Maybe
    it would be interesting to add support for strings.
    """
    assert isinstance(expression, c_ast.BinaryOp), \
        "Expression {} is not binary.".format(expression)
    
    if expression.op == "&&":
        left_result, left_global = evaluate_boolean_expression(expression.left, 
		                                   global_variables,
                                                   local_variables) 
        right_result, right_global = evaluate_boolean_expression(expression.right, 
						   global_variables, 
                                                   local_variables)
	return (left_result and right_result), (left_global or right_global)
    elif expression.op == "||":
        left_result, left_global = evaluate_boolean_expression(expression.left, 
		                                   global_variables,
                                                   local_variables) 
        right_result, right_global = evaluate_boolean_expression(expression.right, 
						   global_variables, 
                                                   local_variables)
	return (left_result or right_result), (left_global or right_global)

    else:
        left_value, is_left_from_global = get_value(expression.left, \
                                                    global_variables, \
                                                    local_variables)
        right_value, is_right_from_global = get_value(expression.right, \
                                                      global_variables, \
                                                      local_variables)
        left_value = int(left_value)
        right_value = int(right_value)
        is_global = is_left_from_global or is_right_from_global
        if expression.op == "==":
            return (left_value == right_value), is_global
        if expression.op == "<":
            return (left_value < right_value), is_global           
        if expression.op == "!=":
            return (left_value != right_value), is_global            
        assert False, "Binary operator {} is not ==, < or !=.".format(expression.op)


def get_function_node(abstract_syntax_tree, function_name):
    """ Given an abstract syntax tree and the name of a function,
    it returns the node in the tree corresponding to that function.
    """
    for node in abstract_syntax_tree.ext:
        if isinstance(node, c_ast.FuncDef):
            if node.decl.name == function_name:
                return node
    assert False, "The function with name {} cannot be found.".format(function_name)


def get_global_state(abstract_syntax_tree):
    """ Given an abstract syntax tree, it returns a dictionary of global variables
    with their values.
    """
    global_variables = dict()
    for node in abstract_syntax_tree.ext:
        if isinstance(node, c_ast.Decl):
            global_variables.update(get_variables_from_declaration(node, \
                                                    global_variables,\
                                                    dict()))
    return global_variables

    
def get_variables_from_declaration(node, global_variables, local_variables):
    """ Given an AST node, it returns the variables found and their values.
    This function was created mainly to transform an array variable 
    into many simple variables.
    """
    new_global_variables = []
    if isinstance(node.type, c_ast.ArrayDecl):
        new_global_variables.extend(array_declaration_to_variables(node.type, \
                                global_variables, local_variables))
    elif isinstance(node.type, c_ast.TypeDecl):
        new_global_variables.extend(simple_declaration_to_variables(node,
                                                                    global_variables,
                                                                    local_variables))
    else:
        assert False, "Declaration type {} is not supported.".format(node.type)
    return new_global_variables

    
def array_declaration_to_variables(node, global_variables, local_variables):
    """ Given an array declaration (TODO: check with an assert this),
    it returns a set of variables that represent the array.
    """
    value, is_global = get_value(node.dim, global_variables, local_variables)
    return [(node.type.declname + str(x), 0) \
            for x in range(int(value))]

def simple_declaration_to_variables(node, global_variables, local_variables):
    """ Given a simple non-array declaration, it returns the variable and the value.
    """
    if node.init == None:
        return [(node.name, None)]
    elif isinstance(node.init, c_ast.UnaryOp):
        return [(node.name, '-' + node.init.expr.value)] # We assume that unary
    # operator expressions are negative integers. TODO: make it correct.
    elif isinstance(node.init, c_ast.Constant):
        return [(node.name, node.init.value)]
    elif isinstance(node.init, c_ast.ID):
        value, is_global = get_value(node.init, global_variables, local_variables)  
        return [(node.name, value)]
    elif isinstance(node.init, c_ast.FuncCall):
        assert False
    else:
        assert False, "Declaration initialization " \
            "{} is not supported.".format(node.init)
    


def process_line(global_variables, thread_id, thread_states, \
                 abstract_syntax_tree, simulate):

    thread_name, thread_instructions, thread_variables = thread_states[thread_id]
#    print "thread {} state {} states {}".format(thread_name, thread_variables,
#                                                thread_states) 
    node = thread_instructions.pop(0)
    is_global = False
    is_counter_example_found = False
    is_assert_found = False
    
    
    if isinstance(node, c_ast.Return):
        if len(thread_instructions) == 0:
            del thread_states[thread_id]
        else:
            variable = node.expr.name
            value, _ = get_variable_value(global_variables, thread_variables,
                                          variable)
            global_variables, thread_variables = set_variable_value(global_variables,
                                                                    thread_variables,
                                                                    'r', value)
#            assert False, "Return from function is not handled yet"
            
    elif isinstance(node, c_ast.UnaryOp):
        variable_name = node.expr.name
        value, is_var_global = get_variable_value(global_variables, \
                                                  thread_variables, variable_name)
        is_global = is_global or is_var_global
        if not simulate:
            global_variables, thread_variables = set_variable_value(global_variables,
                                                                    thread_variables,
                                                                    variable_name, 
                                                                    int(value) + 1)
        elif not is_var_global:
            global_variables, thread_variables = set_variable_value(global_variables,
                                                                    thread_variables,
                                                                    variable_name, 
                                                                    int(value) + 1)
        else:
            thread_instructions.insert(0, node)
                
    elif isinstance(node, c_ast.FuncCall):
        function_name = node.name.name


        if function_name == "pthread_create":

            expr_list = node.args.exprs            
            thread_function_name = node.args.exprs[2].name
            function_node = get_function_node(abstract_syntax_tree,
                                              thread_function_name)
            new_thread_name = get_variable(node.args.exprs[0].expr, global_variables,
                                           thread_variables)
            thread_states.append(("{}-{}".format(thread_function_name, new_thread_name[0]),
                                  [function_node], {}))
            
        elif function_name == "pthread_join":
            expr_list = node.args.exprs                        
            index_number = get_value(node.args.exprs[0], global_variables, \
                                     thread_variables)
            thread_names = [name.split('-')[0] for (name, instructions, variables)
                            in thread_states[1:]]
            
            if str(index_number) in thread_names:
                thread_instructions.insert(0, node)

        elif function_name == "pthread_exit":
            
            if len(thread_instructions) == 0:
                del thread_states[thread_id]
                
        elif function_name == "assert":
            expr_list = node.args.exprs                        
            result, is_using_global = evaluate_boolean_expression(expr_list[0],
                                                                  global_variables, 
                                                                  thread_variables)
            is_global = is_global or is_using_global
	    is_counter_example_found = (not result)
	    is_assert_found = True
            if simulate and is_global:
                thread_instructions.insert(0, node)

        elif function_name == "pthread_mutex_init":
            pass
        
        elif function_name == "pthread_mutex_lock":
            expr_list = node.args.exprs                        
            variable, is_using_global = get_variable(expr_list[0], global_variables,
                                                   thread_variables)
            value, is_using_global = get_variable_value(global_variables,
                                                        thread_variables, variable)
            if int(value) == 0: # mutex unlocked
                global_variables, thread_variables = \
                                set_variable_value(global_variables,
                                                   thread_variables,
                                                   variable, 1) # we lock it
            else: # mutex locked
                thread_instructions.insert(0, node) # we do nothing
        elif function_name == "pthread_mutex_unlock":
            expr_list = node.args.exprs                        
            variable, is_using_global = get_variable(expr_list[0], global_variables,
                                                   thread_variables)
            
            global_variables, thread_variables = \
                                    set_variable_value(global_variables,
                                                       thread_variables,
                                                       variable, 0) # we lock it
            
        else: # any other function
            args = []
            if node.args:
                args = [e.name for e in node.args.exprs]
            function_node = get_function_node(abstract_syntax_tree, function_name)
            if node.args:
                params = [p.name for p in function_node.decl.type.args.params]
                for i, p in enumerate(params):
                    print "args[i] = {}".format(args[i])
                    value, _ = get_variable_value(global_variables,
                                                  thread_variables, args[i])
                    global_variables, thread_variables = \
                                set_variable_value(global_variables,
                                                   thread_variables,
                                                   p, value)
            function_instructions = function_node.body.block_items[:]
            function_instructions.reverse()
            for instruction in function_instructions:
                thread_instructions.insert(0, instruction)
        
    elif isinstance(node, c_ast.FuncDef):
        function_instructions = node.body.block_items[:]
        function_instructions.reverse()
        for instruction in function_instructions:
            thread_instructions.insert(0, instruction)
    
    elif isinstance(node, c_ast.Decl):
        variables = get_variables_from_declaration(node, global_variables, \
                                                   thread_variables)
        for name, value in variables:
            thread_variables[name] = value
            

    elif isinstance(node, c_ast.While):
        result, is_global = evaluate_boolean_expression(node.cond,
                                                        global_variables,
                                                        thread_variables)
#        use_global = use_global or is_global // I don't care on fib example.
        if result:
            thread_instructions.insert(0, node)
            instructions = node.stmt.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)

    elif isinstance(node, c_ast.Assignment):
        variable_name, is_global_variable = get_variable(node.lvalue,
                                                          global_variables,
                                                          thread_variables)
        is_global = is_global or is_global_variable
        value, is_value_from_global = get_value(node.rvalue, global_variables, \
                                                thread_variables)
        is_global = is_global or is_value_from_global
        
        if node.op == "=":
            if not simulate or not is_global:
                global_variables, thread_variables = \
                                    set_variable_value(global_variables,
                                                       thread_variables,
                                                       variable_name,
                                                       int(value))
            else:
                thread_instructions.insert(0, node)
                
        if node.op == "+=":
            old_value, is_value_from_global = get_variable_value(global_variables,
                                                                 thread_variables,
                                                                 variable_name)
            value, is_global_variable = get_value(node.rvalue, global_variables, \
                                                  thread_variables)
            is_global = is_global or is_global_variable
            if not simulate:
                global_variables, thread_variables = \
                                            set_variable_value(global_variables,
                                                               thread_variables,
                                                               variable_name, 
                                                               int(old_value) \
                                                               + int(value))
            else:
                thread_instructions.insert(0, node)
    elif isinstance(node, c_ast.If):
        result, is_global = evaluate_boolean_expression(node.cond,
                                                        global_variables,
                                                        thread_variables)
        if result:
            instructions = node.iftrue.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)
        elif node.iffalse:
            instructions = node.iffalse.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)
            
    else:
        assert False, "{} expression no recognized".format(node)
    return global_variables, thread_states, is_counter_example_found, is_global, \
        is_assert_found

