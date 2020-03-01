import subprocess
from io import StringIO
import re
import textwrap
import util
import argparse

# Parse arguments
parser = argparse.ArgumentParser(description='Analyze .a file or the executable file in .framework to generate macro '
                                             'definitions for the symbols that need to be renamed.',
                                 formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('--ns', dest='ns', required=True, help='New namespace as a symbol prefix.\ne.g. A symbol named '
                                                           '"AFSecurityPolicy", --ns is "ABC", finally you will get '
                                                           '"ABCNamespace.h" and the symbol will be named '
                                                           '"ABCAFSecurityPolicy".')
parser.add_argument('file', help='The file to be analyzed.')
args = parser.parse_args()

# nm -U <file> | c++filt
# How to run command with pipe: https://stackoverflow.com/a/13332300/4968633
ps = subprocess.Popen(('nm', '-U', args.file), stdout=subprocess.PIPE)
result = subprocess.check_output(('c++filt'), stdin=ps.stdout)
ps.wait()
symbols_string = result.decode('utf-8')

ocpp_symbols = set()
oc_category_name_and_method_symbols = set()
oc_category_getter_and_setter_symbols = []
f = StringIO(symbols_string)
while True:
    line = f.readline()
    if line == '':
        break

    # OC/C/C++. For class name, protocol name, global variable, c(++) function name
    # e.g. 0000000000000300 S _OBJC_CLASS_$_SDWebImageCacheKeyFilter
    match = re.fullmatch('[0-9a-f]{16} [STD] (_OBJC_CLASS_\\$|__OBJC_LABEL_PROTOCOL_\\$)?_([_A-Za-z][^_]\\w+)\n', line)
    if match and util.is_apple_symbol(match.group(2)) is False:
        ocpp_symbols.add(match.group(2))

    # OC category. For category name and method name
    # e.g. 0000000000000000 t +[UIImage(GIF) sd_imageWithGIFData:]
    match = re.fullmatch('[0-9a-f]{16} unsigned short [+-]\\[\\w+\\((\\w+)\\) ([\\w:]+)\\]\n', line)
    if match:
        oc_category_name_and_method_symbols.add(match.group(1))  # category name
        # If the method name looks like "- a:b:c", we just need to rewrite "a" part
        method_name = str(match.group(2)).split(':')[0]
        if method_name.startswith('set') and len(method_name) > 3:  # getter & setter
            getter_initial = method_name[3]
            getter_remaining_letters = method_name[4:] if len(method_name) > 4 else ''
            getter1 = getter_initial.lower() + getter_remaining_letters  # e.g. getter is "isUp", setter is "setIsUp"
            getter2 = getter_initial + getter_remaining_letters  # e.g. getter is "HTTPAllowed", setter is "setHTTPAllowed"
            getter_name = ''
            if getter1 in oc_category_name_and_method_symbols:
                getter_name = getter1
            elif getter2 in oc_category_name_and_method_symbols:
                getter_name = getter2
            if len(getter_name) > 0:
                oc_category_name_and_method_symbols.remove(getter_name)
                oc_category_getter_and_setter_symbols.append(getter_name)
                oc_category_getter_and_setter_symbols.append(method_name)
        else:
            oc_category_name_and_method_symbols.add(method_name)

# Avoid duplication of definitions. You may have a class named "AB", and a category named "NSString+AB".
oc_category_name_and_method_symbols.difference_update(ocpp_symbols)

# Write macros into Namespace.h file
result_file_name = args.ns + 'Namespace.h'
with open(result_file_name, 'w') as f:
    content = '''\
    // Two extra layers of indirection for CPP.
    #define {ns}NS_impl2(prefix, symbol) prefix ## symbol
    #define {ns}NS_impl(prefix, symbol) {ns}NS_impl2(prefix, symbol)
    #define {ns}NS(symbol) {ns}NS_impl({ns}, symbol)
    
    // Rewrite all ObjC/C/C++ symbols.
    '''.format(ns=args.ns)
    content = textwrap.dedent(content)

    for s in ocpp_symbols:
        content += '#define {symbol} {ns}NS({symbol})\n'.format(symbol=s, ns=args.ns)

    if len(oc_category_name_and_method_symbols) > 0:
        content += '\n// Rewrite all Objc category symbols.\n'

        for s in oc_category_name_and_method_symbols:
            content += '#define {symbol} {ns}NS({symbol})\n'.format(symbol=s, ns=args.ns)

    if len(oc_category_getter_and_setter_symbols) > 0:
        content += textwrap.dedent('''
        // Attention!
        // Here are all the getter and setter methods in the category. 
        // Due to the special nature of getter and setter method naming, 
        // you may need to double check their correctness.
        ''')
        last_getter = ''
        for s in oc_category_getter_and_setter_symbols:
            if s.startswith('set'):
                content += '#define {symbol} set{ns}{getter}\n'.format(symbol=s, ns=args.ns, getter=last_getter)
                last_getter = ''
            else:
                content += '#define {symbol} {ns}{symbol}\n'.format(symbol=s, ns=args.ns)
                last_getter = s

    f.write(content)
