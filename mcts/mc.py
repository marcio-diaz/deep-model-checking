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
        idx_var_name, is_idx_global = get_variable_value(expression.subscript.name,\
                                                         global_variables, \
                                                         local_variables)
        var_name =  "{}{}".format(expression.name, idx_var_name)
        value, is_var_global = get_variable_value(var_name, global_variables, \
                                                  local_variables)
        is_from_global_variable = (is_idx_global or is_var_global)
        return value, is_from_global_variable
    assert False, "The expression parameter is not a constant, variable or array."

    
def get_variable(expression, global_variables, local_variables):
    """ Given an array or a variable, it returns its name.
    """
    if isinstance(expression, c_ast.ArrayRef):
        value, is_global = get_variable_value(expression.subscript.name, \
                                              global_variables, local_variables)
        return "{}{}".format(expression.name, value), is_global
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

def ggArrayDecl(n):
    return [(n.type.declname+str(x), 0) \
            for x in range(int(n.dim.value))]

def ggTypeDecl(n):
    if n.init == None:
        return [(n.name, None)]
    if isinstance(n.init, c_ast.UnaryOp):
        return [(n.name, '-'+n.init.expr.value)]
    if isinstance(n.init, c_ast.Constant):
        return [(n.name, n.init.value)]
    
def get_vars_from_decl(n):
    global_vars = []
    if isinstance(n.type, c_ast.ArrayDecl):
        global_vars.extend(ggArrayDecl(n.type))
    if isinstance(n.type, c_ast.TypeDecl):
        global_vars.extend(ggTypeDecl(n))
    return global_vars

def get_global_state(ast):
    global_vars = []
    for i, n in enumerate(ast.ext):
        if isinstance(n, c_ast.Decl):
            global_vars.extend(get_vars_from_decl(n))
    return dict(global_vars)


def get_func_node(ast, name):
    for n in ast.ext:
        if isinstance(n, c_ast.FuncDef):
            if n.decl.name == name:
                return n


def process_line(gv, tid, threads, ast, simulate):
#    print gv
    t_name, t_asts, t_locals = threads[tid]
    node = t_asts.pop(0)
    res = 0
    use_global = False
#    print("Processing: {} of T{}".format(node, t_name))
    
    if isinstance(node, c_ast.Return):
#        if t_name == "main":
#            print("Returning from main")
        if len(t_asts) == 0:
            del threads[tid]
            return gv, None, 0, False
    
    if isinstance(node, c_ast.UnaryOp):
        var = node.expr.name
        if var in t_locals.keys():
            t_locals[var] = int(t_locals[var]) + 1
        else:
            use_global = True            
            if not simulate:
                gv[var] = int(gv[var]) + 1
            else:
                t_asts.insert(0, node)
                
    if isinstance(node, c_ast.FuncCall):
        function_name = node.name.name
        expr_list = node.args.exprs
        
        if function_name == "pthread_create":
            fname = node.args.exprs[2].name
            fnode = get_func_node(ast, fname)
            thread_name = get_variable(node.args.exprs[0].expr, gv, t_locals)
            threads.append(("{}".format(fname, thread_name), [fnode], {}))
#            use_global = True
            
        if function_name == "pthread_join":
            idx = node.args.exprs[0].subscript.name
            idx_val = get_variable_value(gv, t_locals, idx)
            thread_names = [name.split('-')[0] for (name, asts, loc) in threads[1:]]
            if str(idx_val) in thread_names:
                t_asts.insert(0, node)

        if function_name == "pthread_exit":
            if len(t_asts) == 0:
                del threads[tid]
                return gv, None, 0, use_global
                
        if function_name == "assert":
            result, is_global = evaluate_boolean_expression(expr_list[0], gv, t_locals)
            use_global = use_global or is_global
            if not simulate:
                if result:
                    return gv, None, -1, use_global
                if not result:
                    return gv, None, 1, use_global
            else:
                t_asts.insert(0, node)
                
    if isinstance(node, c_ast.FuncDef):
        l = node.body.block_items[:]
        l.reverse()
        for x in l:
            t_asts.insert(0, x)
    
    if isinstance(node, c_ast.Decl):
        vars = get_vars_from_decl(node)
        for k, v in vars:
            t_locals[k] = v
            
    if isinstance(node, c_ast.For):
        lvar = node.init.lvalue.name # variable of the for
        val = node.init.rvalue.value # init value of the var
        cond = node.cond.right.value # condition value of the for
        t_locals[lvar] = val
        if t_locals[lvar] < cond:
            node.init.rvalue.value = str(int(val) + 1)
            t_asts.insert(0, node)
            l = node.stmt.block_items[:]
            l.reverse()
            for x in l:
                t_asts.insert(0, x)

    if isinstance(node, c_ast.While):
        cond, is_global = evaluate_boolean_expression(node.cond, gv, t_locals)
#        use_global = use_global or is_global // I don't care on fib example.
        if cond:
            t_asts.insert(0, node)
            l = node.stmt.block_items[:]
            l.reverse()
            for x in l:
                t_asts.insert(0, x)

    if isinstance(node, c_ast.Assignment):
        var_name, is_global = get_variable(node.lvalue, gv, t_locals)
        use_global = (use_global or is_global)
        value, is_global = get_value(node.rvalue, gv, t_locals)
        use_global = (use_global or is_global)
        
        if node.op == "=":
            if not simulate:
                gv, t_locals = set_variable_value(gv, t_locals, var_name, int(value))
            else:
                t_asts.insert(0, node)
                
        if node.op == "+=":
            old_value, is_global = get_variable_value(gv, t_locals, var_name)
            value, is_global = get_value(node.rvalue, gv, t_locals)
            if not simulate:
                gv, t_locals = set_variable_value(gv, t_locals, var_name, \
                                             int(old_value) + int(value))
            else:
                t_asts.insert(0, node)
                
    t = t_name, t_asts, t_locals

    return gv, t, res, use_global

    
def execute(gv, ts, ast):
    # choose one thread at random
    ts = [t for t in ts if t != None]
    tid = randint(0, len(ts)-1)
    t = ts[tid]
    if len(t[1]) > 0:
        gv, t, ce = process_line(gv, tid, ts, ast)
        if ce == 1:
            return "counterexample"
        if t != None:
            ts[tid] = t
#    print "*"*80
#    print global_vars
#    print threads
#    print "*"*80
    return gv, ts, ast
    # execute its line
    # if finish with that thread remove it
    # modify global and locals
            
def algorithm():
    script, filename = argv
    ast = parse_file(filename, use_cpp=True)

    for k in range(10000000):
        global_vars = get_global_state(ast)
        threads = [("main", [get_func_node(ast, "main")], {})]
        deep = 0
        while True:
            r = execute(global_vars, threads, ast)
            if r == "counterexample":
                print "Counter-example found :). # deep = {}\n".format(deep)
                return
            global_vars, threads, ast = r
            if len(threads) == 0:
                print "SAFE. # deep = {}".format(deep)
                break
            deep = deep + 1

if __name__ == "__main__":
    algorithm()
