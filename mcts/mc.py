from random import randint
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
    assert False, "The expression parameter is not a constant, variable or array."

    
def get_variable(expression, global_variables, local_variables):
    """ Given an array or a variable, it returns its name.
    """
    if isinstance(expression, c_ast.ArrayRef):
        value, is_global = get_variable_value(global_variables, local_variables, 
						  expression.subscript.name)
	return "{}{}".format(expression.name.name, value), is_global
    if isinstance(expression, c_ast.ID):
        return expression.name, False
    assert False, "The expression parameter is not a variable or an array."

    
def evaluate_boolean_expression(expression, global_variables, local_variables):
    """ Given a boolean expression it returns its value. TODO: make it work
    for literals. Also, it only support integers inside the expression. Maybe
    it would be interesting to add support for strings.
    """
    assert isinstance(expression, c_ast.BinaryOp), "Expression in is not binary."
    
    if expression.op == "&&":
        return (evaluate_boolean_expression(expression.left, global_variables, \
                                            local_variables) \
                and evaluate_boolean_expression(expression.right, global_variables, \
                                                local_variables))
    elif expression.op == "||":
        return (evaluate_boolean_expression(expression.left, global_variables,
                                            local_variables) \
                or evaluate_boolean_expression(expression.right, global_variables, \
                                               local_variables))
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
            return left_value == right_value, is_global
        if expression.op == "<":
            return left_value < right_value, is_global           
        if expression.op == "!=":
            return left_value != right_value, is_global            
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
    global_state = []
    for node in abstract_syntax_tree.ext:
        if isinstance(node, c_ast.Decl):
            global_state.extend(get_variables_from_declaration(node))
    return dict(global_state)

    
def get_variables_from_declaration(node):
    """ Given an AST node, it returns the variables found and their values.
    This function was created mainly to transform an array variable 
    into many simple variables.
    """
    global_variables = []
    if isinstance(node.type, c_ast.ArrayDecl):
        global_variables.extend(array_declaration_to_variables(node.type))
    elif isinstance(node.type, c_ast.TypeDecl):
        global_variables.extend(simple_declaration_to_variables(node))
    else:
        assert False, "Declaration type is not supported."
    return global_variables

    
def array_declaration_to_variables(node):
    """ Given an array declaration (TODO: check with an assert this),
    it returns a set of variables that represent the array.
    """
    return [(node.type.declname + str(x), 0) \
            for x in range(int(node.dim.value))]

def simple_declaration_to_variables(node):
    """ Given a simple non-array declaration, it returns the variable and the value.
    """
    if node.init == None:
        return [(node.name, None)]
    elif isinstance(node.init, c_ast.UnaryOp):
        return [(node.name, '-' + node.init.expr.value)] # We assume that unary
    # operator expressions are negative integers. TODO: make it correct.
    elif isinstance(node.init, c_ast.Constant):
        return [(node.name, node.init.value)]
    else:
        assert False, "Declaration initialization " \
            "{} is not supported.".format(node.init)
    


def process_line(global_variables, thread_id, thread_states, \
                 abstract_syntax_tree, simulate):
    thread_name, thread_instructions, thread_variables = thread_states[thread_id]
    node = thread_instructions.pop(0)
    is_global = False
    is_counter_example_found = False
    is_assert_found = False
    
    
    if isinstance(node, c_ast.Return):
        if len(thread_instructions) == 0:
            del thread_states[thread_id]
    
    if isinstance(node, c_ast.UnaryOp):
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
                
    if isinstance(node, c_ast.FuncCall):
        function_name = node.name.name
        expr_list = node.args.exprs
        
        if function_name == "pthread_create":
            thread_function_name = node.args.exprs[2].name
            function_node = get_function_node(abstract_syntax_tree,
                                              thread_function_name)
            new_thread_name = get_variable(node.args.exprs[0].expr, global_variables,
                                           thread_variables)
            thread_states.append(("{}".format(thread_function_name, new_thread_name),
                                  [function_node], {}))
            
        if function_name == "pthread_join":
            index_variable_name = node.args.exprs[0].subscript.name
            index_number = get_variable_value(global_variables, thread_variables,
                                              index_variable_name)
            thread_names = [name.split('-')[0] for (name, instructions, variables)
                            in thread_states[1:]]
            
            if str(index_number) in thread_names:
                thread_instructions.insert(0, node)

        if function_name == "pthread_exit":
            if len(thread_instructions) == 0:
                del thread_states[thread_id]
                
        if function_name == "assert":
            result, is_using_global = evaluate_boolean_expression(expr_list[0],
                                                                  global_variables, 
                                                                  thread_variables)
            is_global = is_global or is_using_global

            if not simulate:
                is_counter_example_found = not result
                is_assert_found = True
            else:
                is_assert_found = True                
                is_counter_example_found = not result
                thread_instructions.insert(0, node)
                
    if isinstance(node, c_ast.FuncDef):
        function_instructions = node.body.block_items[:]
        function_instructions.reverse()
        for instruction in function_instructions:
            thread_instructions.insert(0, instruction)
    
    if isinstance(node, c_ast.Decl):
        variables = get_variables_from_declaration(node)
        for name, value in variables:
            thread_variables[name] = value
            

    if isinstance(node, c_ast.While):
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

    if isinstance(node, c_ast.Assignment):
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
                
    return global_variables, thread_states, is_counter_example_found, is_global, \
        is_assert_found

