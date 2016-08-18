
def transform(line):
    if line[0:7] == "#define":
        words =  line.split()
        variable = words[1]
        value = words[2]
        return "int {} = {};".format(variable, value)
    elif line[0:8] == "#include":
        return ""
    elif line[0:6] == "extern":
        return ""
    elif line[0:15] == "void __VERIFIER":
        return ""
    
    return line

def clean(source_code):
    cleaned_source_code = "typedef int pthread_t;"
    for line in source_code:
        cleaned_source_code += transform(line)
    return cleaned_source_code

if __name__ == "__main__":
    import sys
    filename = sys.argv[1]
    with open(filename) as f:
        source_code = f.readlines()
        cleaned_source_code = clean(source_code)
        print cleaned_source_code

