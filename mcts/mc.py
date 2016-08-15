from random import randint
from itertools import product, chain
from pycparser import c_parser, c_ast, parse_file, c_generator
from sys import argv




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


def process_line(gv, tid, threads, ast):
#    print(threads)
    t_name, t_asts, t_locals = threads[tid]
    node = t_asts.pop(0)
    res = 0
#        print("Processing: {} of T{}".format(node, t_name))
    
    if isinstance(node, c_ast.Return):
#        if t_name == "main":
#            print("Returning from main")
        if len(t_asts) == 0:
            del threads[tid]
            return gv, None, 0
    
    if isinstance(node, c_ast.UnaryOp):
        var = node.expr.name
        if var in t_locals.keys():
            t_locals[var] = int(t_locals[var]) + 1
        else:
            gv[var] = int(gv[var]) + 1

    if isinstance(node, c_ast.FuncCall):
        if node.name.name == "pthread_create":
            fname = node.args.exprs[2].name
            fnode = get_func_node(ast, fname)
            idx = node.args.exprs[0].expr.subscript.name
            idx_val = get_var_value(gv, t_locals, idx)
            threads.append((fname+"-"+str(idx_val), [fnode], {}))

            
        if node.name.name == "pthread_join":
            idx = node.args.exprs[0].subscript.name
            idx_val = get_var_value(gv, t_locals, idx)
            thread_names = [name.split('-')[0] for (name, asts, loc) in threads[1:]]
            if str(idx_val) in thread_names:
                t_asts.insert(0, node)
            
        if node.name.name == "assert":

            var = node.args.exprs[0].left.name
            var_val = get_var_value(gv, t_locals, var)
            val = node.args.exprs[0].right.value            
            if node.args.exprs[0].op == "==":
                if int(var_val) != int(val):
                    return gv, None, 1
                else:
                    res = -1
            if node.args.exprs[0].op == "<":
                if int(var_val) >= int(val):
                    return gv, None, 1
                else:
                    res = -1
            if node.args.exprs[0].op == "!=":
                if int(var_val) == int(val):
                    return gv, None, 1
                else:
                    res = -1
            
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
        var = node.cond.left.name
        val = node.cond.right.value
        var_val = get_var_value(gv, t_locals, var)

        if int(var_val) < int(val):
            t_asts.insert(0, node)
            l = node.stmt.block_items[:]
            l.reverse()
            for x in l:
                t_asts.insert(0, x)

    if isinstance(node, c_ast.Assignment):

        if isinstance(node.lvalue, c_ast.ArrayRef):
            idx = node.lvalue.subscript.name
            idx_val = get_var_value(gv, t_locals, idx)
            varl = node.lvalue.name.name + str(idx_val)
        else:
            varl = node.lvalue.name

            
        if isinstance(node.rvalue, c_ast.ArrayRef):
            idx = node.rvalue.subscript.name
            idx_val = get_var_value(gv, t_locals, idx)
            varr = node.rvalue.name.name + str(idx_val)
            val = get_var_value(gv, t_locals, varr)
        else:
            val = node.rvalue.value
        if  node.op == "=":
            gv, t_locals = set_var_value(gv, t_locals, varl, int(val))
        if node.op == "+=":
            val_old = get_var_value(gv, t_locals, varl)            
            gv, t_locals = set_var_value(gv, t_locals, varl, int(val_old) + int(val))
    t = t_name, t_asts, t_locals

    return gv, t, res

def get_var_value(global_vars, local_vars, name):
    if name in local_vars.keys():
        return local_vars[name]
    if name in global_vars.keys():
        return global_vars[name]
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
        if ce:
            return ce
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
