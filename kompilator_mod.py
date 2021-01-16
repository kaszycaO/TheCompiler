#!usr/bin/python3

from ply import yacc
import sys
import lexer

tokens = lexer.tokens

# symbol table: (name) or (name, tab_start, tab_end)
sym_tab = {}

# 0 -> write
data_offset = 0

# main code
code = []
code_offset = 0

# for -> for_jmp
labels = [('END', "")]

# repeat until
command = {}
prev_command_line = 0;

# pid, code position
dead_code = []
code_start = 0

# registers

regs_status = {
    'a' : 0,
    'b' : 0,
    'c' : 0,
    'd' : 0,
    'e' : 0,
    'f' : 0,
}

# comments
comments = []

# ERROR color
ERROR = '\033[91m'

#----------------------------- CUSTOM EXCEPTIONS -------------------------------#

class FatalError(Exception):

    def __init__(self, m, line):

        message = "\n" + ERROR
        message += m + str(line)
        self.message = message
        super().__init__(self.message)

class SyntaxError(Exception):

    def __init__(self, line, value):

        message = "\n" + ERROR
        message += "Nieprawidłowy znak: '" + str(value) + "' w linii " + str(line)

        self.message = message
        super().__init__(self.message)

class OutOfBoundsError(Exception):

    def __init__(self, index, tab):

        message = "\n" + ERROR
        message += "Indeks " + str(index) + " poza zakresem tablicy"\
                        ": " + str(tab)
        self.message = message
        super().__init__(self.message)


#------------------------------ SYMBOL TABLE ----------------------------------#

def add_to_sym_tab(sym_name, is_tab, t_start, t_itr, offset, used=False, initialized=False, modified=0, value=-1, local=False):

    if sym_name not in sym_tab:
        sym_tab.update({sym_name: [is_tab, t_start, t_itr, offset, used, initialized, modified, value, local]})
    else:
        raise FatalError("Zmienna została już zadeklarowana: ", sym_name)

def get_sym(sym_name):
    return sym_tab[sym_name]

def check_if_exists(sym_name):
    if sym_name not in sym_tab:
        raise FatalError("Zmienna nie została jeszcze zadeklarowana: ", sym_name)

def make_initialized(sym_name):
    global sym_tab
    sym_tab[sym_name][5] = True

def make_modified(sym_name):
    global sym_tab
    sym_tab[sym_name][6] += 1

def check_if_val_possible(sym_name):
    global sym_tab

    if sym_name in sym_tab:
        mod = sym_tab[sym_name][6]
        if mod == 1:
            return True
        else:
            return False
    else:
        return False

def check_if_used(sym_name):
    global sym_tab
    return sym_tab[sym_name][4]

def make_used(sym_name):
    global sym_tab
    if sym_name in sym_tab:
        sym_tab[sym_name][4] = True

def add_value_to_sym_tab(sym_name, value, index=-1):
    global sym_tab
    if value != -1:
        if index == -1:
            sym_tab[sym_name][7] = value
        else:
            mod_index = index - sym_tab[sym_name][1]
            if sym_tab[sym_name][2] < 20:
                if sym_tab[sym_name][7] == -1:
                    sym_tab[sym_name][7] = [ None for i in range(sym_tab[sym_name][2] + 1) ]
                    sym_tab[sym_name][7][mod_index] = value
                else:
                    sym_tab[sym_name][7][mod_index] = value

def get_value(sym_name, index=-1):
    global sym_tab
    if not str(sym_name).isdigit():
        if check_if_val_possible(sym_name):
            if index == -1: # PID
                return sym_tab[sym_name][7]
            else: # TAB
                if sym_tab[sym_name][7] != -1:
                    if str(index).isdigit():
                        mod_index = index - sym_tab[sym_name][1]
                        return sym_tab[sym_name][7][mod_index]
                    else:
                        val = get_value(index)
                        if val != -1:
                            mod_index = val - sym_tab[sym_name][1]
                            return sym_tab[sym_name][7][mod_index]
        return -1

    else:
        return sym_name

def check_if_initialized(sym_name, line):
    global sym_tab
    sym = get_sym(sym_name)

    if sym[5] == False:
        raise FatalError("Niezainicjowana zmienna: " + sym_name + " w linii: ", line)

def check_if_modified(sym_name):
    global sym_tab
    if sym_name in sym_tab:
        mod = sym_tab[sym_name][6]
        if mod == 0:
            return False
        else:
            return True
    else:
        return True

def data_location():
    global data_offset
    data_offset += 1
    return data_offset

#------------------    LABELS & CODE MODYFICATIONS  ---------------------------#

def generate_code(command):
    global code

    code.append(command)

def gen_label():
    global code
    return len(code)

def generate_comment(comment):
    global code
    global comments

    comments.append((('(---' + comment + '---)'), gen_label()))

def assign_comments():

    global comments
    global code

    for el in comments:
        code.insert(el[1], el[0])

def create_temp_variable():
    global sym_name
    offset = data_location()
    sym_name = "TEMP_" + str(offset)
    sym_tab.update({sym_name: [0, 0, 0, offset, True]})
    return offset

def delete_temp_variable(sym_name):
    del sym_tab[sym_name]

def insert_code(start_index, injection_index):
    global code

    comments = 0

    helper = code[injection_index:]
    code = code[:injection_index]

    helper.reverse()

    for el in helper:
        code.insert(start_index, el)

    return len(helper)

def delete_local_vars(sym_name):
    global sym_tab
    del sym_tab[sym_name]

def clear_code(index):
    global code
    global code_start
    helper = code[:code_start]
    code = code[index:]
    code = helper + code

def check_if_dead_code():
    global dead_code

    if len(dead_code) > 0:
        temp = dead_code[0]
        for el in dead_code:
            if check_if_modified(el[0]):
                return (False, -1)
        return (True, temp[1])
    else:
        return (False, -1)

def expand_loop(code, itr):
    global code_start

    if itr < 0:
        return -1
    elif itr == 0:
        return 0
    else:
        for i in range(itr):
            for el in code:
                generate_code(el)
                if el == "GET a":
                    code_start = gen_label()
        return 1

def check_if_expand(val_1, val_2, type):

    if val_1[0] == "num" and val_2[0] == "num":
        if type == "TO":
            itr = val_2[1] - val_1[1]
        else:
            itr = val_1[1] - val_2[1]
    else:
        check_1 = get_value(val_1[1], val_1[2])
        check_2 = get_value(val_2[1], val_1[2])
        if check_1 == -1 or check_2 == -1:
            return (False, -1)
        if type == "TO":
            itr = check_2 - check_1
        else:
            itr = check_1 - check_2

    if itr < 21:
        return (True, itr)
    else:
        return (False, -1)


def update_register(register, value):
    global regs_status

    regs_status[register] = value


#-------------------     VARIABLES & MEMORY   ---------------------------------#

def prepare_num(num, register):


    generate_code(("RESET " + register))
        # update_register(register, 0)
    helper = []
    while num != 0:
        if num % 2 == 1:
            helper.append(("INC " + register))
            num = num - 1
        else:
            helper.append(("SHL " + register))
            num = num // 2

    if len(helper) != 0:
        helper.reverse()
        for el in helper:
            generate_code(el)

def prepare_best_num(value, register):
    global regs_status
    best = register
    print(register, " INIT ", value)
    val = abs(regs_status[register] - value)
    true_value = value - regs_status[register]
    for el in regs_status:
        check = abs(regs_status[el] - value)
        if check < val:
            best = el
            val = check
            true_value = regs_status[el] - value
    print(best, " BEST ", val)
    if val < 20 and best != register:
        # update_register(best, value)
        generate_code("RESET " + best)
        if true_value >= 0:
            for _ in range(val):
                generate_code("INC " + best)
        else:
            for _ in range(val):
                generate_code("DEC " + best)
    else:
        prepare_num(value, register)
        # update_register(register, value)

def get_tab_value(sym_name, arr, register):

    # Array:  tab(arr); arr != const
    sym = get_sym(sym_name)

    off = sym[3]
    start = sym[1]

    arr_sym = get_sym(arr)
    arr_off = arr_sym[3]

    # mam a z p(a)
    prepare_num(arr_off, register)
    generate_code("RESET e")
    generate_code("LOAD " + 'e' + " " + register)
    prepare_num(start, register)
    generate_code("SUB e " + register)
    prepare_num(off, register)
    # jestem na p(arr)
    generate_code("ADD " + register + " " + 'e')

def load_var(sym_name, arr=-1, register='a'):

    # sym_name (type, name, args)
    sym = get_sym(sym_name)
    # pid
    if arr == -1:
        itr = sym[3]
        prepare_num(itr, register)
    else:
        if str(arr).isdigit():  # tab(const)
            itr = sym[3] + (arr - sym[1])

            if itr < 0 or itr > sym[2] + sym[1] + sym[3]:
                raise OutOfBoundsError(arr, sym_name)

            prepare_num(itr, register)


        else:   # tab(pid)
            get_tab_value(sym_name, arr, register)

def assign_to_mem(sym_name, arr=-1):

    # get data from load_var

    if str(sym_name).isdigit():  # num
        prepare_num(sym_name, 'b')
    else:
        sym = get_sym(sym_name)

        if arr == -1: # pid
            itr = sym[3]
            prepare_num(itr, 'a')

        else:
            if str(arr).isdigit():  # tab(const)
                itr = sym[3] + (arr - sym[1])

                if itr < 0 or itr > sym[2] + sym[1] + sym[3]:
                    raise OutOfBoundsError(arr, sym_name)

                prepare_num(itr, 'a')
            else:   # tab(pid)
                get_tab_value(sym_name, arr, 'a')

        generate_code("LOAD b a")

def print_memory():
    global data_offsetload

    # ONLY FOR DEBUGING
    generate_code("RESET a")

    for _ in range(data_offset + 1):
        generate_code("PUT a")
        generate_code("INC a")

#---------------------   MATH OPERATIONS --------------------------------------#

def perform_add(arg_1, arg_2):
    # b musi być na outpucie
    if arg_1[0] == 'num':
        make_used(arg_2[1])
        if arg_1[1] < 20:
            load_var(arg_2[1], arg_2[2], 'b')
            generate_code("LOAD b b")
            for _ in range(arg_1[1]):
                generate_code("INC b")
        else:
            prepare_num(arg_1[1], 'b')
            load_var(arg_2[1], arg_2[2])
            generate_code("LOAD a a")
            generate_code("ADD b a")

    if arg_2[0] == 'num':
        make_used(arg_1[1])
        if arg_2[1] < 20:
            load_var(arg_1[1], arg_1[2], 'b')
            generate_code("LOAD b b")
            for _ in range(arg_2[1]):
                generate_code("INC b")
        else:
            prepare_num(arg_2[1], 'b')
            load_var(arg_1[1], arg_1[2])
            generate_code("LOAD a a")
            generate_code("ADD b a")

    if arg_1[0] != 'num' and arg_2[0] != 'num':
        make_used(arg_1[1])
        make_used(arg_2[1])
        load_var(arg_1[1], arg_1[2], 'f')
        generate_code("LOAD f f")
        load_var(arg_2[1], arg_2[2], 'b')
        generate_code("LOAD b b")
        generate_code("ADD b f")

def perform_sub(arg_1, arg_2):
    # b musi być na outpucie
    if arg_1[0] == 'num':
        make_used(arg_2[1])
        load_var(arg_2[1], arg_2[2])
        generate_code("LOAD a a")
        prepare_num(arg_1[1], 'b')
        generate_code("SUB b a")

    if arg_2[0] == 'num':
        make_used(arg_1[1])
        if arg_2[1] < 20:
            load_var(arg_1[1], arg_1[2], 'b')
            generate_code("LOAD b b")
            for _ in range(arg_2[1]):
                generate_code("DEC b")
        else:
            prepare_num(arg_2[1], 'a')
            load_var(arg_1[1], arg_1[2], 'b')
            generate_code("LOAD b b")
            generate_code("SUB b a")

    if arg_1[0] != 'num' and arg_2[0] != 'num':
        make_used(arg_1[1])
        make_used(arg_2[1])
        load_var(arg_1[1], arg_1[2], 'b')
        generate_code("LOAD b b")
        load_var(arg_2[1], arg_2[2], 'f')
        generate_code("LOAD f f")
        generate_code("SUB b f")

def prepare_condition(value, register):

    if value[0] == 'num':
        prepare_num(value[1], register)
    else:
        make_used(value[1])
        load_var(value[1], value[2], register)
        generate_code(("LOAD " + register + " " + register))



################################################################################
#--------------------------------  COMPILER -----------------------------------#
################################################################################

precedence = (

    ('left', 'ADD', 'SUB'),
    ('left', 'MUL', 'DIV', 'MOD'),
    ('nonassoc', 'EQ', 'NEQ', 'GT', 'LT', 'GEQ', 'LEQ'),

)

def p_program(p):
    '''
        program     : DECLARE declarations BEGIN commands END
                    | BEGIN commands END
    '''
    print(sym_tab)
    dead = check_if_dead_code()
    if dead[0]:
        clear_code(dead[1])
    assign_comments()
    generate_code("HALT")
    p[0] = code

#--------------------------------  DECLARATIONS -------------------------------#

def p_declarations_vars(p):
    '''
        declarations     : declarations SEP pidentifier
    '''
    add_to_sym_tab(p[3], False, 0, 0, data_location())

def p_declarations_arrays(p):
    '''
        declarations     : declarations SEP pidentifier LPAREN NUMBER COLON NUMBER RPAREN
    '''
    global data_offset
    if p[5] > p[7]:
        raise FatalError("Nieprawidłowa deklaracja tablicy: ", p[3])
    add_to_sym_tab(p[3], True, p[5], p[7] - p[5], data_location())
    data_offset += p[7] - p[5]

def p_declarations_var(p):
    '''
        declarations    : pidentifier
    '''
    add_to_sym_tab(p[1], False, 0, 0, data_location())

def p_declarations_array(p):
    '''
        declarations     : pidentifier LPAREN NUMBER COLON NUMBER RPAREN
    '''
    global data_offset
    if p[3] > p[5]:
        raise FatalError("Nieprawidłowa deklaracja tablicy: ", p[1])
    add_to_sym_tab(p[1], True, p[3], p[5] - p[3], data_location())
    data_offset += p[5] - p[3]

#--------------------------------  COMMANDS -----------------------------------#

def p_commands_comands(p):
    '''
        commands         : commands command
    '''
    global prev_command_line

    p[0] = gen_label()
    start = prev_command_line
    prev_command_line = gen_label() + 1
    command.update({p.linespan(2)[0] : start})

def p_commands_comand(p):
    '''
        commands         : command
    '''
    global prev_command_line

    p[0] = gen_label()
    start = prev_command_line
    prev_command_line = gen_label() + 1
    command.update({p.linespan(1)[0] : start})

def p_command_assign(p):
    '''
        command         : identifier ASSIGN expression SEMICOLON
    '''
    if p[1][0] == 'num':
        raise FatalError("Nieprawidłowe przypisanie w linii: ", p.lineno(1))

    if get_sym(p[1][1])[8] == True:
        raise FatalError("Nadpisanie zmiennej lokalnej w linii: ", p.lineno(1))

    # Tab
    if p[1][2] != -1:
        val = get_value(p[1][2])
        if val != -1:
            add_value_to_sym_tab(p[1][1], p[3], val)
    else: #PID / NUM
        add_value_to_sym_tab(p[1][1], p[3], p[1][2])

    load_var(p[1][1], p[1][2])
    generate_code("STORE b a")
    make_initialized(p[1][1])
    make_modified(p[1][1])

def p_command_if_else(p):
    '''
        command         :  IF condition THEN commands ELSE commands ENDIF
    '''
    global code

    code.insert(p[4], ("JUMP " + str(gen_label() - p[4] + 1)))
    labels.pop(-1)
    while labels[-1][0] != "END":
        if labels[-1][1] == "commands_NO":
            code[labels[-1][0]] = "JUMP " + str(p[4] - labels[-1][0] + 1)
        elif labels[-1][1] == "commands_YES":
            code[labels[-1][0]] = "JUMP " + str(p[2] - labels[-1][0])
        labels.pop(-1)

def p_command_if(p):
    '''
        command         :  IF condition THEN commands ENDIF
    '''
    global code

    labels.pop(-1)
    while labels[-1][0] != "END":
        if labels[-1][1] == "commands_NO":
            code[labels[-1][0]] = "JUMP " + str(gen_label() - labels[-1][0])
        elif labels[-1][1] == "commands_YES":
            code[labels[-1][0]] = "JUMP " + str(p[2] - labels[-1][0])
        labels.pop(-1)

def p_command_while(p):
    '''
        command         :  WHILE condition DO commands ENDWHILE
    '''
    global code
    labels.pop(-1)
    while labels[-1][0] != "END":
        if labels[-1][1] == "commands_NO":
            code[labels[-1][0]] = "JUMP " + str(gen_label() - labels[-1][0] + 1)
        elif labels[-1][1] == "commands_START":
            com = "JUMP -" + str(gen_label() - labels[-1][0])
            generate_code(com)
        elif labels[-1][1] == "commands_YES":
            code[labels[-1][0]] = "JUMP " + str(p[2] - labels[-1][0])
        labels.pop(-1)

def p_command_repeat(p):
    '''
        command         :  REPEAT commands UNTIL condition SEMICOLON
    '''
    global code
    start = command[p.linespan(2)[0]] - 1
    labels.pop(-1)
    while labels[-1][0] != "END":
        if labels[-1][1] == "commands_NO":
            code[labels[-1][0]] = "JUMP -" + str(labels[-1][0] - start)
        elif labels[-1][1] == "commands_YES":
            code[labels[-1][0]] = "JUMP " + str(gen_label() - labels[-1][0])
        labels.pop(-1)

def p_iterator(p):
    '''
        iterator : pidentifier
    '''
    add_to_sym_tab(p[1], False, 0, 0, data_location(), False, local=True)
    make_initialized(p[1])
    p[0] = (p[1], gen_label())

def p_command_for_to(p):
    '''
        command         :  FOR iterator FROM value TO value DO commands ENDFOR
    '''
    global code

    if p[2][0] == p[4][1] or p[2][0] == p[6][1]:
        raise FatalError("Użycie niezadeklarowanej zmiennej w pętli w linii: ", p.lineno(1))

    injection_index = gen_label()
    expand = check_if_expand(p[4], p[6], "TO")
    if expand[0] and check_if_used(p[2][0]) == False:
        e = expand_loop(code[p[2][1]:injection_index], expand[1])
        if e == -1:
            code = code[:p[2][1]]
        delete_local_vars(p[2][0])
    else:
        # init iterator
        assign_to_mem(p[4][1], p[4][2])
        load_var(p[2][0])
        generate_code("STORE b a")
        if p[6][0] != 'num':
            load_var(p[6][1], p[6][2], 'd')
            generate_code("LOAD d d")
        else:
            prepare_num(p[6][1], 'd')

        generate_code("RESET f")
        generate_code("ADD f d")
        generate_code("INC f")
        generate_code("SUB f b")

        jump = (gen_label() - injection_index) + p[2][1]
        off = create_temp_variable()
        prepare_num(off, 'a')
        generate_code("STORE d a")

        helper = insert_code(p[2][1], injection_index)


        # koniec przedziału
        prepare_num(off, 'a')
        generate_code("LOAD d a")
        load_var(p[2][0])
        generate_code("LOAD b a")
        generate_code("INC b")
        generate_code("STORE b a")

        # warunek końca
        generate_code("RESET c")
        generate_code("ADD c d")
        generate_code("INC c") # i = <x, y>
        generate_code("LOAD a a")
        generate_code("SUB c a")
        generate_code("JZERO c 2")
        generate_code("JUMP -" + str(gen_label() - (p[2][1] + helper)))
        code.insert(jump, ("JZERO f " + str(gen_label() - jump + 1)))
        delete_local_vars(p[2][0])
        delete_temp_variable(("TEMP_" + str(off)))

def p_command_for_downto(p):
    '''
        command         : FOR iterator FROM value DOWNTO value DO commands ENDFOR
    '''
    global code

    injection_index = gen_label()

    expand = check_if_expand(p[4], p[6], "DOWNTO")
    if expand[0] and check_if_used(p[2][0]) == False:
        e = expand_loop(code[p[2][1]:injection_index], expand[1])
        if e == -1:
            code = code[:p[2][1]]
        delete_local_vars(p[2][0])
    else:
        # init
        assign_to_mem(p[4][1], p[4][2])
        load_var(p[2][0])
        generate_code("STORE b a")
        if p[6][0] != 'num':
            load_var(p[6][1], p[6][2], 'd')
            generate_code("LOAD d d")
        else:
            prepare_num(p[6][1], 'd')

        generate_code("RESET f")
        generate_code("ADD f b")
        generate_code("INC f")
        generate_code("SUB f d")
        jump = (gen_label() - injection_index) + p[2][1]

        off = create_temp_variable()
        prepare_num(off, 'a')
        generate_code("STORE d a")


        helper = insert_code(p[2][1], injection_index)

        prepare_num(off, 'a')
        generate_code("LOAD d a")

        # TODO load a improvement
        load_var(p[2][0])

        # warunek końca
        generate_code("RESET c")
        generate_code("LOAD a a")
        generate_code("ADD c a")
        generate_code("SUB c d")

        # decrement
        load_var(p[2][0])
        generate_code("LOAD b a")
        generate_code("DEC b")
        generate_code("STORE b a")

        generate_code("JZERO c 2")
        generate_code("JUMP -" + str(gen_label() - (p[2][1] + helper)))
        code.insert(jump, ("JZERO f " + str(gen_label() - jump + 1)))

        delete_local_vars(p[2][0])
        delete_temp_variable(("TEMP_" + str(off)))

def p_command_read(p):
    '''
        command         : READ identifier SEMICOLON
    '''
    global code_start

    if get_sym(p[2][1])[8] == True:
        raise FatalError("Nadpisanie zmiennej lokalnej w linii: ", p.lineno(1))

    load_var(p[2][1], p[2][2])
    generate_code("GET a")
    make_initialized(p[2][1])
    code_start = gen_label()

def p_command_write(p):
    '''
        command         :   WRITE value SEMICOLON
    '''
    p[0] = gen_label()


    if p[2][0] == 'num':
        prepare_num(p[2][1], 'f')
        generate_code("RESET e")
        generate_code("STORE f e")
        generate_code("PUT e")

    elif p[2][0] == 'pid':
        dead_code.append((p[2][1], gen_label()))
        sym = get_sym(p[2][1])
        prepare_num(sym[3], 'a')
        generate_code("PUT a")
    elif p[2][0] == 'array':
        load_var(p[2][1], p[2][2])
        generate_code("PUT a")

#--------------------------------  EXPRESSIONS --------------------------------#

def p_expression_value(p):
     '''
        expression  : value

     '''
     if p[1][0] != 'num':
         make_used(p[1][1])
         check_if_initialized(p[1][1], p.lineno(1))
         if p[1][0] == 'array' and str(p[1][2]).isdigit() == False:
             check_if_initialized(p[1][2], p.lineno(1))

         val = get_value(p[1][1], p[1][2])
         if val != -1:
            p[0] = val
         else:
             p[0] = -1
     else:
         p[0] = p[1][1]

     assign_to_mem(p[1][1], p[1][2])

def p_expression_add(p):
     '''
        expression  : value ADD value
     '''
     if p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] + p[3][1])
        p[0] = p[1][1] + p[3][1]
     else:
        perform_add(p[1], p[3])
        p[0] = -1

def p_expression_sub(p):
     '''
        expression  : value SUB value

     '''
     if p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(max(p[1][1] - p[3][1], 0))
        p[0] = max(p[1][1] - p[3][1], 0)
     else:
         val_1 = get_value(p[1][1], p[1][2])
         val_2 = get_value(p[3][1], p[3][2])
         perform_sub(p[1], p[3])
         # if val_1 != -1 and val_2 != -1:
         #     p[0] = max(val_1 - val_2, 0)
         # else:
         p[0] = -1

def p_expression_mul(p):
    '''
        expression  : value MUL value
    '''
    val_1 = get_value(p[1][1], p[1][2])
    val_2 = get_value(p[3][1], p[3][2])

    if (p[1][0] == 'num' and p[3][0] == 'num'):
        assign_to_mem(p[1][1] * p[3][1])
        p[0] = p[1][1] * p[3][1]
    else:
        p[0] = -1
        if p[1][0] != 'num' and p[3][0] != 'num':
            make_used(p[1][1])
            make_used(p[3][1])
            load_var(p[1][1], p[1][2], 'b')
            generate_code("RESET f")
            generate_code("LOAD b b")
            load_var(p[3][1], p[3][2])
            generate_code("LOAD a a")
            # warunek końca pętli
            generate_code("JZERO a 11")
            generate_code("DEC a")
            # jeżeli a - 1 = 0
            generate_code("JZERO a 10")
            generate_code("INC a")
            # jeżeli a % 2 == 1 -> DEC a
            generate_code("JODD a 4")
            # jeżeli a % 2 == 0-> SHR a
            generate_code("SHR a")
            generate_code("SHL b")
            # powrót do warunku pętli
            generate_code("JUMP -6")
            generate_code("DEC a")
            generate_code("ADD f b")
            # powrót do warunku pętli
            generate_code("JUMP -9")
            generate_code("RESET b") # a = 0
            # dodanie temp
            generate_code("ADD b f")

        else:
            helper = []
            if p[1][0] == 'num':
                make_used(p[3][1])
                temp = p[1][1]
                load_var(p[3][1], p[3][2])
            else:
                make_used(p[1][1])
                temp = p[3][1]
                load_var(p[1][1], p[3][2])

            if temp != 0:
                generate_code("RESET b")
                generate_code("RESET f")
                generate_code("LOAD b a")

                while temp != 1:
                    if temp % 2 == 1:
                        generate_code("ADD f b")
                        temp = temp - 1
                    else:
                        generate_code("SHL b")
                        temp = temp // 2
                generate_code("ADD b f")
            else:
                generate_code("RESET b")

def p_expression_div(p):
     '''
        expression  : value DIV value

     '''
     val_1 = get_value(p[1][1], p[1][2])
     val_2 = get_value(p[3][1], p[3][2])
     if p[1][1] == 0 or p[3][1] == 0:
         assign_to_mem(0)
         p[0] = 0
     elif p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] // p[3][1])
        p[0] = p[1][1] // p[3][1]
     else:
        p[0] = -1
        if p[1][0] != 'num' and p[3][0] != 'num':
            load_var(p[1][1], p[1][2], 'd')
            generate_code("LOAD d d")
            load_var(p[3][1], p[3][2])
            generate_code("LOAD a a")
            make_used(p[1][1])
            make_used(p[3][1])
        if p[1][0] == 'num':
            prepare_num(p[1][1], 'd')
            load_var(p[3][1], p[3][2])
            generate_code("LOAD a a")
            make_used(p[3][1])
        if p[3][0] == 'num':
            load_var(p[1][1], p[1][2], 'd')
            generate_code("LOAD d d")
            prepare_num(p[3][1], 'a')
            make_used(p[1][1])


        # ALGORITM
        # b / a : num / den

        # init
        generate_code("RESET b") # wynik
        generate_code("JZERO a 23") # czy a = 0
        generate_code("RESET e") # place
        generate_code("INC e") # place

        # pętla I
        generate_code("RESET f") # helper w pętli
        generate_code("ADD f d")
        generate_code("SHR f")
        generate_code("INC f")
        generate_code("SUB f a")
        generate_code("JZERO f 4") # wyjście z pętli
        generate_code("SHL e")
        generate_code("SHL a")
        generate_code("JUMP -8") # ponowne sprawdzenie warunku

        # pętla II
        generate_code("JZERO e 11") # wyjście z pętli
        generate_code("RESET f") # helper w ifie
        generate_code("ADD f d")
        generate_code("INC f")
        generate_code("SUB f a")
        generate_code("JZERO f 3") # if nie
        generate_code("SUB d a") # if tak
        generate_code("ADD b e")
        generate_code("SHR e")
        generate_code("SHR a")
        # powrót na początek pętli
        generate_code("JUMP -10")

def p_expression_mod(p):
     '''
        expression  : value MOD value

     '''
     if p[1][1] == 0 or p[3][1] == 0:
         assign_to_mem(0)
         p[0] = 0
     elif p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] % p[3][1])
        p[0] = p[1][1] % p[3][1]
     else:
       p[0] = -1
       if p[1][0] != 'num' and p[3][0] != 'num':
           load_var(p[1][1], p[1][2], 'b')
           generate_code("LOAD b b")
           load_var(p[3][1], p[3][2])
           generate_code("LOAD a a")
           make_used(p[1][1])
           make_used(p[3][1])
       if p[1][0] == 'num':
           prepare_num(p[1][1], 'b')
           load_var(p[3][1], p[3][2])
           generate_code("LOAD a a")
           make_used(p[3][1])
       if p[3][0] == 'num':
           load_var(p[1][1], p[1][2], 'b')
           generate_code("LOAD b b")
           prepare_num(p[3][1], 'a')
           make_used(p[1][1])

       # ALGORITM
       # b / a : num / den

       # init
       generate_code("JZERO a 22") # czy a = 0
       generate_code("RESET e") # place
       generate_code("INC e") # place
       # pętla I
       generate_code("RESET f") # helper w pętli
       generate_code("ADD f b")
       generate_code("SHR f")
       generate_code("INC f")
       generate_code("SUB f a")
       generate_code("JZERO f 4") # wyjście z pętli
       generate_code("SHL e")
       generate_code("SHL a")
       generate_code("JUMP -8") # ponowne sprawdzenie warunku

       # pętla II
       generate_code("JZERO e 11") # wyjście z pętli
       generate_code("RESET f") # helper w ifie
       generate_code("ADD f b")
       generate_code("INC f")
       generate_code("SUB f a")
       generate_code("JZERO f 2") # if nie
       generate_code("SUB b a") # if tak
       generate_code("SHR e")
       generate_code("SHR a")
       generate_code("JUMP -9") # powrót na początek pętli
       # wynik w b
       generate_code("RESET b")

#--------------------------------  CONDITIONS ---------------------------------#

def p_condition_eq(p):
     '''
        condition  :  value EQ value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e b")
     generate_code("SUB e f")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     generate_code("ADD e f")
     generate_code("SUB e b")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     # code.append("code") # <- tak
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_neq(p):
     '''
        condition  : value NEQ value
     '''
     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e b")
     generate_code("SUB e f")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     generate_code("ADD e f")
     generate_code("SUB e b")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_gt(p):
     '''
        condition  : value GT value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e b")
     generate_code("SUB e f")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_lt(p):
     '''
        condition  : value LT value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e f")
     generate_code("SUB e b")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_geq(p):
     '''
        condition  : value GEQ value
     '''
     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e b")
     generate_code("INC e")
     generate_code("SUB e f")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie (potencjalne przyspieszenie)
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_leq(p):
     '''
        condition  : value LEQ value
     '''
     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     generate_code("RESET e")
     generate_code("ADD e f")
     generate_code("INC e")
     generate_code("SUB e b")
     generate_code("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     generate_code("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     generate_code("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

#--------------------------------  VALUE -------------------------------------#

def p_value_num(p):
    '''
       value  : NUMBER
    '''
    p[0] = ('num', p[1], -1)

def p_value_identifier(p):
    '''
       value   : identifier
    '''
    check_if_initialized(p[1][1], p.lineno(1))
    p[0] = p[1]

#--------------------------------  IDENTIFIER ---------------------------------#

def p_identifier_pid(p):
    '''
       identifier  : pidentifier
    '''
    check_if_exists(p[1])
    sym = get_sym(p[1])
    if sym[0] == False:
        p[0] = ('pid', p[1], -1)
    else:
        raise FatalError(("Zmienna " + str(p[1]) + " jest tablicą. Linia: "), p.lineno(1))

def p_identifier_array(p):
    '''
        identifier  : pidentifier LPAREN NUMBER RPAREN
    '''
    check_if_exists(p[1])
    sym = get_sym(p[1])
    if sym[0] == True:
        if p[3] - sym[1] > sym[2] or p[3] - sym[1] < 0:
            raise OutOfBoundsError(p[3], p[1])
        p[0] = ('array', p[1], p[3])
    else:
        raise FatalError(("Zmienna " + str(p[1]) + " nie jest tablicą. Linia: "), p.lineno(1))

def p_identifier_par(p):
    '''
       identifier  : pidentifier LPAREN pidentifier RPAREN
    '''
    check_if_exists(p[1])
    check_if_exists(p[3])
    make_used(p[3])
    make_used(p[1])
    if get_sym(p[1])[0] == True:
        val = get_value(p[3])
        if val == -1:
            p[0] = ('array', p[1], p[3])
        else:
            p[0] = ('array', p[1], val)
    else:
        raise FatalError(("Zmienna " + str(p[1]) + " nie jest tablicą. Linia: "), p.lineno(1))


#--------------------------------  ERRORS -------------------------------------#

def p_error(p):
    if p != None:
        raise SyntaxError(p.lineno, p.value)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        parser = yacc.yacc()
        parsed = []
        with open(sys.argv[1], "r") as f:
            parsed = parser.parse(f.read(),tracking=True)
        with open(sys.argv[2], "w+") as f:
            for el in parsed:
                f.write(el + "\n")
    else:
        sys.stderr.write("Nieprawidłowe parametry wejściowe!\n")
