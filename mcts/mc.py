from random import randint
from itertools import product, chain
from pycparser import c_parser, c_ast, parse_file, c_generator
from sys import argv

def get_value(expression, global_variables, thread_local_states):
    """ Given a constant, variable or array expression, 
    it returns its value. It also indicates if the returned value comes
    from reading a global variable or not.
    """
    is_from_global_variable = False
    if isinstance(expression, c_ast.ID):
        return get_var_value(global_variables, thread_local_states,\
                             expression.name)
    elif isinstance(expression, c_ast.Constant):
        return expression.value, is_from_global_variable
    elif isinstance(expression, c_ast.ArrayRef):
        idx_var_name, is_idx_global = get_var_value(expression.subscript.name,\
                                                    global_variables, \
                                                    thread_local_states)
        var_name =  "{}{}".format(expression.name, idx_var_name)
        value, is_var_global = get_var_value(var_name, global_variables, \
                                             thread_local_states)
        is_from_global_variable = (is_idx_global or is_var_global)
        return value, is_from_global_variable
    assert False, "The expression parameter is not a constant, variable or array."

def get_variable(expr, gv, t_locals):
    if isinstance(expr, c_ast.ArrayRef):
        value, is_global = get_var_value(expr.subscript.name, gv, t_locals)
        return "{}{}".format(expr.name, value), is_global
    if isinstance(expr, c_ast.ID):
        return expr.name, False
    
    assert False
    
def eval_bool_expr(expr, gv, t_locals):
    assert isinstance(expr, c_ast.BinaryOp), "Expression in assert is not binary."
    
    if expr.op == "&&":
        return (eval_bool_expr(expr.left, gv, t_locals)\
                and eval_bool_expr(expr.right, gv, t_locals))
    elif expr.op == "||":
        return (eval_bool_expr(expr.left, gv, t_locals) \
                or eval_bool_expr(expr.right, gv, t_locals))
    else:
        value1, is_global1 = get_value(expr.left, gv, t_locals)
        value2, is_global2 = get_value(expr.right, gv, t_locals)
#        print "evaluating {} {} {} from {} {}".format(value1, expr.op, value2,
#                                                      expr.left, expr.right)

        value1 = int(value1)
        value2 = int(value2)
        is_global = (is_global1 or is_global2)
        
        if expr.op == "==":
            return value1 == value2, is_global
        if expr.op == "<":
            return value1 < value2, is_global           
        if expr.op == "!=":
            return value1 != value2, is_global            
        assert False

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
            idx_val = get_var_value(gv, t_locals, idx)
            thread_names = [name.split('-')[0] for (name, asts, loc) in threads[1:]]
            if str(idx_val) in thread_names:
                t_asts.insert(0, node)

        if function_name == "pthread_exit":
            if len(t_asts) == 0:
                del threads[tid]
                return gv, None, 0, use_global
                
        if function_name == "assert":
            result, is_global = eval_bool_expr(expr_list[0], gv, t_locals)
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
        cond, is_global = eval_bool_expr(node.cond, gv, t_locals)
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
                gv, t_locals = set_var_value(gv, t_locals, var_name, int(value))
            else:
                t_asts.insert(0, node)
                
        if node.op == "+=":
            old_value, is_global = get_var_value(gv, t_locals, var_name)
            value, is_global = get_value(node.rvalue, gv, t_locals)
            if not simulate:
                gv, t_locals = set_var_value(gv, t_locals, var_name, \
                                             int(old_value) + int(value))
            else:
                t_asts.insert(0, node)
                
    t = t_name, t_asts, t_locals

    return gv, t, res, use_global

def get_var_value(global_vars, local_vars, name):
    if name in local_vars.keys():
        return local_vars[name], False
    if name in global_vars.keys():
        return global_vars[name], True
    assert(False)

def set_var_value(global_vars, local_vars, name, value):
    if name in local_vars.keys():
        local_vars[name] = value
        return global_vars, local_vars
    if name in global_vars.keys():
        global_vars[name] = value
        return global_vars, local_vars
    assert(False)
    
    
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
