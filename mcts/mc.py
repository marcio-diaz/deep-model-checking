from random import randint, randrange
from itertools import product, chain
from pycparser import c_parser, c_ast, parse_file, c_generator
from sys import argv

DEBUG = False

def get_variable_value(global_variables, local_variables, variable_name, subscript):
    """ Given a name of a variable it returns its value.
    """
    is_global = False
    if variable_name in local_variables.keys():
        if subscript == None:
            return local_variables[variable_name], is_global
        else:
            return local_variables[variable_name][subscript], is_global
    if variable_name in global_variables.keys():
        is_global = True
        if subscript == None:
            return global_variables[variable_name], is_global
        else:
            return global_variables[variable_name][subscript], is_global
    assert False, "There is no variable with {} name.".format(variable_name)

    
def set_variable_value(global_variables, local_variables, variable_name, subscript,
                       value):
    """ Given a name of a variable and a value, it sets the variable
    to that value.
    """
    if variable_name in local_variables.keys():

        if subscript == None:
            local_variables[variable_name] = value
        else:

            local_variables[variable_name][subscript] = value
        return global_variables, local_variables
    if variable_name in global_variables.keys():
        if subscript == None:
            global_variables[variable_name] = value
        else:
            global_variables[variable_name][subscript] = value
        return global_variables, local_variables
    
    assert False, "There is no variable with {} name.".format(variable_name)

    
def get_value(expression, global_variables, local_variables):
    """ Given a constant, variable or array expression, 
    it returns its value. It also indicates if the returned value comes
    from reading a global variable or not.
    """
    is_from_global_variable = False
    if isinstance(expression, c_ast.ID):
        return get_variable_value(global_variables, local_variables, expression.name,
                                  None)
    elif isinstance(expression, c_ast.Constant):
        return expression.value, is_from_global_variable
    elif isinstance(expression, c_ast.ArrayRef):
        idx_var_name, is_idx_global = get_variable_value(global_variables, 
                                                         local_variables, 
							 expression.subscript.name,
                                                         None)
#        var_name =  "{}{}".format(expression.name.name, idx_var_name)
        variable = expression.name.name
        array, is_var_global = get_variable_value(global_variables, 
                                                  local_variables, variable, None)
        value = array[idx_var_name]
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
						  expression.subscript.name, None)
	return expression.name.name, expression.subscript.name, is_global
    if isinstance(expression, c_ast.ID):
        return expression.name, None, False
    if isinstance(expression, c_ast.UnaryOp):
        return expression.expr.name, None, True

    assert False, "The expression parameter is not a variable or an array."

    
def evaluate_boolean_expression(expression, global_variables, local_variables):
    """ Given a boolean expression it returns its value. TODO: make it work
    for literals. Also, it only support integers inside the expression. Maybe
    it would be interesting to add support for strings.
    """
    
    if expression.op == "!":
        result, is_global = evaluate_boolean_expression(expression.expr,
                                                        global_variables,
                                                        local_variables)
        return (not result), is_global
    elif expression.op == "&&":
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
        if DEBUG:
            print "Evaluating {} {} {}.".format(left_value, right_value,
                                                expression.op)
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
    return [(node.type.declname, [0 for i in range(int(value))])]
#    print "Array declaration {}".format(node.type.declname)

#    return [(node.type.declname + str(x), 0) \
#            for x in range(int(value))]

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

    #thread_name, thread_instructions, thread_variables = thread_states[thread_id]

    thread_name, thread_instructions, thread_frames = thread_states[thread_id]
    if len(thread_frames) > 0:
        current_frame = thread_frames.pop()
    else:
        current_frame = (dict(), dict())
    thread_variables = current_frame[0]
    args_to_params_map = current_frame[1]

    
    node = thread_instructions.pop(0)
    if DEBUG:
        print "Processing in thread {}, id {} of {}.".format(thread_name,
                                                             thread_id,
                                                             len(thread_states))

#        print "Instructions: {}".format([i for (n, i, v) in thread_states])
    is_global = False
    is_counter_example_found = False
    is_assert_found = False
    is_blocked = False
    
    if isinstance(node, c_ast.Return):
        if DEBUG:
            print "RETURN:",
        if len(thread_instructions) == 0:
            if DEBUG:
                print "ending thread."
            del thread_states[thread_id]
        else:
            if node.expr and len(thread_frames) - 1 > 0:
                value, _ = get_value(node.expr, global_variables, thread_variables)
                if DEBUG:
                    print "value {}.".format(value)
                if DEBUG:
                    print "thread frames on return {}".format(thread_frames)

                prev_thread_variables, _ = thread_frames[len(thread_frames)-1]
                set_variable_value(global_variables, prev_thread_variables,
                                   'r', None, value)

            if len(thread_frames) > 0:
                prev_thread_variables, _ = thread_frames[len(thread_frames)-1]

                # We update the previous frame before returning.
                for arg, param in args_to_params_map.items():
                    value, _ = get_variable_value(global_variables,
                                                  thread_variables, param, None)
                    set_variable_value(global_variables,
                                       prev_thread_variables, arg, None, value)
            
#            assert False, "Return from function is not handled yet"
            
    elif isinstance(node, c_ast.UnaryOp):
        operator = node.op
        variable_name = node.expr.name
        if DEBUG:
            print "Operador unario {} en variable {}".format(operator, variable_name)

        value, is_var_global = get_variable_value(global_variables, \
                                                  thread_variables,
                                                  variable_name, None)
        is_global = is_global or is_var_global
        if not simulate:
            if operator != "p--":
                global_variables, thread_variables = set_variable_value(global_variables,
                                                                        thread_variables,
                                                                        variable_name,
                                                                        None,
                                                                        int(value) + 1)
                if DEBUG:
                    print "setting it to {}".format(int(value)+1)

            elif operator == "p--":
                global_variables, thread_variables = set_variable_value(global_variables,
                                                                        thread_variables,
                                                                        variable_name,
                                                                        None,
                                                                        int(value) - 1)
                if DEBUG:
                    print "setting it to {}".format(int(value)-1)


                
        elif not is_var_global:
            if DEBUG:
                print "setting it to {}".format(int(value)+1)
            if operator != "p--":
                global_variables, thread_variables = set_variable_value(global_variables,
                                                                        thread_variables,
                                                                        variable_name,
                                                                        None,
                                                                        int(value) + 1)
                if DEBUG:
                    print "setting it to {}".format(int(value)+1)
                
            elif operator == "p--":
                global_variables, thread_variables = set_variable_value(global_variables,
                                                                        thread_variables,
                                                                        variable_name,
                                                                        None,
                                                                        int(value) - 1)
                if DEBUG:
                    print "setting it to {}".format(int(value)-1)
                
        else:
            if DEBUG:
                print "doing nothing."

            thread_instructions.insert(0, node)
                
    elif isinstance(node, c_ast.FuncCall):
        # restore old frame
        thread_frames.append(current_frame)
        
        function_name = node.name.name
        if DEBUG:
            print "Calling function {}.".format(function_name)
        if function_name == "pthread_create":

            expr_list = node.args.exprs            
            thread_function_name = node.args.exprs[2].name
            function_node = get_function_node(abstract_syntax_tree,
                                              thread_function_name)
            new_thread_name = get_variable(node.args.exprs[0].expr, global_variables,
                                           thread_variables)
            thread_states.append(("{}-{}".format(thread_function_name,
                                                 new_thread_name[0]),
                                  [function_node], []))
            
        elif function_name == "pthread_join":
            expr_list = node.args.exprs
            index_number, _ = get_value(node.args.exprs[0], global_variables, \
                                     thread_variables)
            if index_number != None:
                thread_names = [name.split('-')[0] for (name, instructions,variables)
                                in thread_states[1:]]
                if DEBUG:
                    print "thread id {} thread names {}".format(index_number,
                                                                thread_names)
                if str(index_number) in thread_names:
                    thread_instructions.insert(0, node)
                    is_blocked = True
            else: # we index by name of the variable
                thread_id = node.args.exprs[0].name
                thread_names = [name.split('-')[1] for (name, instructions,variables)
                                in thread_states if not name == "main"]
                if DEBUG:
                    print "thread id {} thread names {}".format(thread_id,
                                                                thread_names)
                if thread_id in thread_names:
                    thread_instructions.insert(0, node)
                    is_blocked = True

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
            variable, subscript, is_using_global = get_variable(expr_list[0],
                                                                global_variables,
                                                                thread_variables)
            value, is_using_global = get_variable_value(global_variables,
                                                        thread_variables, variable,
                                                        subscript)
            if int(value) == 0: # mutex unlocked
                if DEBUG:
                    print "Mutex unlocked."
                global_variables, thread_variables = \
                                set_variable_value(global_variables,
                                                   thread_variables,
                                                   variable, subscript, 1) # we lock it
            else: # mutex locked
                if DEBUG:
                    print "Mutex locked."
                thread_instructions.insert(0, node) # we do nothing
                is_blocked = True
        elif function_name == "pthread_mutex_unlock":
            expr_list = node.args.exprs                        
            variable, subscript, is_using_global = get_variable(expr_list[0],
                                                                global_variables,
                                                                thread_variables)
            
            global_variables, thread_variables = \
                                    set_variable_value(global_variables,
                                                       thread_variables,
                                                       variable, subscript, 0) # we lock it
            
        elif function_name == "printf":
            pass
        
        else: # any other function
            new_thread_variables = dict()
            args = []
            if node.args:
                args = [e.name for e in node.args.exprs]
            function_node = get_function_node(abstract_syntax_tree, function_name)
            if node.args:
                params = [p.name for p in function_node.decl.type.args.params]
                for i, p in enumerate(params):

                    value, _ = get_variable_value(global_variables,
                                                  thread_variables, args[i], None)
                    new_thread_variables[p] = value
            else:
                params = []
            function_instructions = function_node.body.block_items[:]
            function_instructions.reverse()
            for instruction in function_instructions:
                thread_instructions.insert(0, instruction)

            args = []
            params = []
            if node.args:
                for i in range(len(node.args.exprs)):
                    if isinstance(function_node.decl.type.args.params[i].type, c_ast.PtrDecl):
                        args.append(node.args.exprs[i].name)
                        params.append(function_node.decl.type.args.params[i].name)
            # Add the new frame.
            new_args_to_params_map = dict(zip(args, params))
            new_frame = (new_thread_variables, new_args_to_params_map)

            thread_frames.append(new_frame)
        
    elif isinstance(node, c_ast.FuncDef):
        if DEBUG:
            print "Function definition."
        function_instructions = node.body.block_items[:]
        function_instructions.reverse()
        for instruction in function_instructions:
            thread_instructions.insert(0, instruction)
    
    elif isinstance(node, c_ast.Decl):
        variables = get_variables_from_declaration(node, global_variables, \
                                                   thread_variables)
        if DEBUG:
            print "Declaring variables {}".format(variables)
        
        for name, value in variables:
            thread_variables[name] = value

    elif isinstance(node, c_ast.While):
        result, is_global = evaluate_boolean_expression(node.cond,
                                                        global_variables,
                                                        thread_variables)
        if DEBUG:
            print "while {}.".format(result)
        
#        use_global = use_global or is_global // I don't care on fib example.
        if result:
            thread_instructions.insert(0, node)
            instructions = node.stmt.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)

    elif isinstance(node, c_ast.Assignment):
        variable_name, subscript, is_global_variable = get_variable(node.lvalue,
                                                          global_variables,
                                                          thread_variables)

        is_global = is_global or is_global_variable
        value, is_value_from_global = get_value(node.rvalue, global_variables, \
                                                thread_variables)
        if subscript != None:
            subs_value, _ = get_variable_value(global_variables,
                                               thread_variables,
                                               subscript,
                                               None)
            subs_value = int(subs_value)
        else:
            subs_value = None
            
        if DEBUG:
            print "Assignment: {} {} {}".format(variable_name, node.op, value)
        is_global = is_global or is_value_from_global
        if node.op == "=":
            if not simulate or not is_global:
                global_variables, thread_variables = \
                                    set_variable_value(global_variables,
                                                       thread_variables,
                                                       variable_name,
                                                       subs_value,
                                                       int(value))
            else:
                thread_instructions.insert(0, node)
                
        if node.op == "+=":
            old_value, is_value_from_global = get_variable_value(global_variables,
                                                                 thread_variables,
                                                                 variable_name,
                                                                 subs_value)
            value, is_global_variable = get_value(node.rvalue, global_variables, \
                                                  thread_variables)
            is_global = is_global or is_global_variable
            if not simulate or not is_global:
                global_variables, thread_variables = \
                                            set_variable_value(global_variables,
                                                               thread_variables,
                                                               variable_name,
                                                               subs_value,
                                                               int(old_value) \
                                                               + int(value))
            elif is_global:
                thread_instructions.insert(0, node)
    elif isinstance(node, c_ast.If):
        result, is_global = evaluate_boolean_expression(node.cond,
                                                        global_variables,
                                                        thread_variables)
        if DEBUG:
            print "IF",
        if result:
            if DEBUG:
                print "executing true branch."
            instructions = node.iftrue.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)
        elif node.iffalse:
            if DEBUG:
                print "executing false branch."
            instructions = node.iffalse.block_items[:]
            instructions.reverse()
            for instruction in instructions:
                thread_instructions.insert(0, instruction)
        else:
            if DEBUG:
                print "executing false branch (jumping)."
    else:
        assert False, "{} expression no recognized".format(node)


    if not isinstance(node, c_ast.Return) and not isinstance(node, c_ast.FuncCall):
        thread_frames.append(current_frame)




    return global_variables, thread_states, is_counter_example_found, is_global, \
        is_assert_found, is_blocked

