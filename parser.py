from ply import yacc
import sys
import lexer

tokens = lexer.tokens

# symbol table: (name) or (name, tab_start, tab_end)
sym_tab = {}
# 0 -> write
data_offset = 0
# for -> for_jmp
labels = [('END', "")]
command = {}
prev_command_line = 0;
code_offset = 0
code = []


def add_to_sym_tab(sym_name, is_tab, t_start, t_itr, offset, local=False):
    # print(sym_name," ",is_tab)
    if sym_name not in sym_tab:
        sym_tab.update({sym_name: [is_tab, t_start, t_itr, offset, local]})
    else:
        raise Exception("%s already defined!", sym_name)

def get_sym(sym_name):
    return sym_tab[sym_name]

def check_if_exists(sym_name):
    if sym_name not in sym_tab:
        raise Exception("%s is undeclared", sym_name)


def data_location():
    global data_offset
    data_offset += 1
    return data_offset

def gen_label():
    global code
    return len(code)

def get_label():
    return labels[-1]

def create_temp_variable():
    global sym_name
    offset = data_location()
    sym_name = "TEMP_" + str(offset)
    sym_tab.update({sym_name: [0, 0, 0, offset, True]})
    return offset

def delete_temp_variable(sym_name):
    del sym_tab[sym_name]

def insert_code(helper, start_index):
    global code
    helper.reverse()
    for el in helper:
        code.insert(start_index, el)

def prepare_num(num, register, store=True):

    # usunąć do starej wersji
    code.append(("RESET " + register))
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
            code.append(el)

def assign_to_tab(sym_name, arr, register):

    sym = get_sym(sym_name)
    off = sym[3]
    start = sym[1]
    itr = sym[2]

    arr_sym = get_sym(arr)
    arr_off = arr_sym[3]


    # mam a z p(a)
    prepare_num(arr_off, register, False)
    code.append("RESET e")
    code.append("LOAD " + 'e' + " " + register)
    # biorę p(a)
    # jestem na p(0)
    prepare_num(off - start, register, False)
    # jestem na p(arr)
    code.append("ADD " + register + " " + 'e')

def load_var(sym_name, arr=-1):

    # sym_name (type, name, args)
    sym = get_sym(sym_name)
    # pid
    if arr == -1:
        itr = sym[3]
        prepare_num(itr, 'a')
    else:
        if str(arr).isdigit():  # tab(const)
            itr = sym[3] + (arr - sym[1])

            if itr < 0 or itr > sym[2] + sym[1] + sym[3]:
                raise Exception("Index " + str(arr) + " out of bounds in table: " + sym_name)

            prepare_num(itr, 'a')


        else:   # tab(pid)
            assign_to_tab(sym_name, arr, 'a')

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
                    raise Exception("Index out of bounds in table: " + sym_name)

                prepare_num(itr, 'a')
            else:   # tab(pid)
                assign_to_tab(sym_name, arr, 'a')

        code.append("LOAD b a")

def math_opperation(arg_1, arg_2, opp):
    # b musi być na outpucie
    # code.append("( " + opp + str(arg_1[1]) + " " + str(arg_2[1]) + ' )')
    if arg_1[0] == 'num':
        prepare_num(arg_1[1], 'b')
        load_var(arg_2[1], arg_2[2])
        code.append("LOAD a a")
        code.append(opp + "a b")
        code.append("RESET b")
        code.append("ADD b a") # minus się wykrzaczył

    if arg_2[0] == 'num':
        prepare_num(arg_2[1], 'b')
        load_var(arg_1[1], arg_1[2])
        code.append("LOAD a a")
        code.append(opp + "a b")
        code.append("RESET b")
        code.append("ADD b a")

    if arg_1[0] != 'num' and arg_2[0] != 'num':
        load_var(arg_1[1], arg_1[2])
        code.append("RESET f")
        code.append("LOAD f a")
        load_var(arg_2[1], arg_2[2])
        code.append("RESET b")
        code.append("LOAD b a")
        code.append(opp + "f b")
        code.append("RESET b")
        code.append("ADD b f")

def print_memory():
    global data_offset
    code.append("RESET a")
    for _ in range(data_offset + 1):
        code.append("PUT a")
        code.append("INC a")

def prepare_condition(value, register):

    if value[0] == 'num':
        prepare_num(value[1], register)
    else:
        load_var(value[1], value[2])
        code.append(("RESET " + register))
        code.append(("LOAD " + register + " a"))

def delete_local_vars(sym_name):
    global sym_tab

    del sym_tab[sym_name]


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
    code.append("HALT")
    for el in code:
        print(el)
    p[0] = code

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
    add_to_sym_tab(p[1], True, p[3], p[5] - p[3], data_location())
    data_offset += p[5] - p[3]

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
        raise Exception("Nieprawidłowe przypisanie!")

    # code.append("( Init " + str(p[1][1]) +  ' )')
    # assign_to_mem(p[3][1], p[3][2])
    load_var(p[1][1], p[1][2])
    code.append("STORE b a")

def p_command_if_else(p):
    '''
        command         :  IF condition THEN commands ELSE commands ENDIF
    '''
    global code
    code.insert(p[4], ("JUMP " + str(gen_label() - p[4] + 1)))
    labels.pop(-1)
    while labels[-1][0] != "END":
        # print("IF ELSE, ", labels)
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
        # print("IF, ", labels)
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
        # print("WHILE, ", labels)
        if labels[-1][1] == "commands_NO":
            code[labels[-1][0]] = "JUMP " + str(gen_label() - labels[-1][0] + 1)
        elif labels[-1][1] == "commands_START":
            com = "JUMP -" + str(gen_label() - labels[-1][0])
            code.append(com)
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
    add_to_sym_tab(p[1], False, 0, 0, data_location(), True)
    p[0] = (p[1], gen_label())

def p_command_for_to(p):
    '''
        command         :  FOR iterator FROM value TO value DO commands ENDFOR
    '''
    global code
    helper = []
    injection_index = gen_label()

    # init
    assign_to_mem(p[4][1], p[4][2])
    load_var(p[2][0])
    code.append("STORE b a")
    if p[6][0] != 'num':
        load_var(p[6][1], p[6][2])
        code.append("LOAD d a")
    else:
        prepare_num(p[6][1], 'd')
    off = create_temp_variable()
    prepare_num(off, 'a')
    code.append("STORE d a")

    helper = code[injection_index:]
    code = code[:injection_index]
    insert_code(helper, p[2][1])

    prepare_num(off, 'a')
    code.append("LOAD d a")
    load_var(p[2][0])
    code.append("LOAD b a")
    code.append("INC b")
    code.append("STORE b a")

    # warunek końca
    code.append("RESET c")
    code.append("ADD c d")
    code.append("INC c") # i = <x, y>
    code.append("LOAD a a")
    code.append("SUB c a")
    code.append("JZERO c 2")
    code.append("JUMP -" + str(gen_label() - (p[2][1] + len(helper))))

    delete_local_vars(p[2][0])
    delete_temp_variable(("TEMP_" + str(off)))




def p_command_for_downto(p):
    '''
        command         : FOR iterator FROM value DOWNTO value DO commands ENDFOR
    '''
    global code
    # TODO local global !!!!
    # Nie można modyfikować 2. value w trakcie !!!!!!! / Nie działa zagnieżdżanie
    helper = []
    injection_index = gen_label()

    # init
    assign_to_mem(p[4][1], p[4][2])
    load_var(p[2][0])
    code.append("STORE b a")
    if p[6][0] != 'num':
        load_var(p[6][1], p[6][2])
        code.append("LOAD d a")
    else:
        prepare_num(p[6][1], 'd')

    off = create_temp_variable()
    prepare_num(off, 'a')
    code.append("STORE d a")

    helper = code[injection_index:]
    code = code[:injection_index]
    insert_code(helper, p[2][1])

    prepare_num(off, 'a')
    code.append("LOAD d a")

    # TODO load a improvement
    load_var(p[2][0])

    # warunek końca
    code.append("RESET c")
    code.append("LOAD a a")
    code.append("ADD c a")
    code.append("SUB c d")

    # decrement
    load_var(p[2][0])
    code.append("LOAD b a")
    code.append("DEC b")
    code.append("STORE b a")

    code.append("JZERO c 2")
    code.append("JUMP -" + str(gen_label() - (p[2][1] + len(helper))))

    delete_local_vars(p[2][0])
    delete_temp_variable(("TEMP_" + str(off)))

def p_command_read(p):
    '''
        command         : READ identifier SEMICOLON
    '''
    off = get_sym(p[2][1])[3]
    prepare_num(off, 'a', False)
    code.append("GET a")

def p_command_write(p):
    '''
        command         :   WRITE value SEMICOLON
    '''
    p[0] = gen_label()
    # TODO loadvar
    if p[2][0] == 'num':
        # code.append("RESET a")
        prepare_num(p[2][1], 'f', False)
        code.append("RESET e")
        code.append("STORE f e")
        code.append("PUT e")

    elif p[2][0] == 'pid':
        # code.append("RESET a")
        sym = get_sym(p[2][1])
        prepare_num(sym[3], 'a', False)
        code.append("PUT a")
    elif p[2][0] == 'array':
        load_var(p[2][1], p[2][2])
        code.append("PUT a")

def p_expression_value(p):
     '''
        expression  : value

     '''
     assign_to_mem(p[1][1], p[1][2])

def p_expression_add(p):
     '''
        expression  : value ADD value
     '''
     if p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] + p[3][1])
     else:
         math_opperation(p[1], p[3], "ADD ")

def p_expression_sub(p):
     '''
        expression  : value SUB value

     '''
     if p[1][0] == 'num' and p[3][0] == 'num':

        assign_to_mem(max(p[1][1] - p[3][1], 0))
     else:
         math_opperation(p[1], p[3], "SUB ")

def p_expression_mul(p):
    '''
        expression  : value MUL value
    '''
    # code.append("( MUL " + str(p[1][1]) + str(p[3][1]) + ' )')
    if p[1][0] == 'num' and p[3][0] == 'num':
       assign_to_mem(p[1][1] * p[3][1])
    else:
        if p[1][0] != 'num' and p[3][0] != 'num':
            load_var(p[1][1], p[1][2])
            code.append("RESET b")
            code.append("RESET f")
            code.append("LOAD b a")
            load_var(p[3][1], p[3][2])
            code.append("LOAD a a")
            # warunek końca pętli
            code.append("JZERO a 13")
            code.append("RESET e")
            code.append("INC e")
            code.append("SUB a e")
            # jeżeli a - 1 = 0
            code.append("JZERO a 10")
            code.append("INC a")
            # jeżeli a % 2 == 1 -> DEC a
            code.append("JODD a 4")
            # jeżeli a % 2 == 0-> SHR a
            code.append("SHR a")
            code.append("SHL b")
            # powrót do warunku pętli
            code.append("JUMP -6")
            code.append("DEC a")
            code.append("ADD f b")
            # powrót do warunku pętli
            code.append("JUMP -9")
            code.append("RESET b") # a = 0
            # dodanie temp
            code.append("ADD b f")

        else:
            helper = []
            if p[1][0] == 'num':
                temp = p[1][1]
                load_var(p[3][1], p[3][2])
            else:
                temp = p[3][1]
                load_var(p[1][1], p[3][2])

            code.append("RESET b")
            code.append("RESET f")
            code.append("LOAD b a")

            while temp != 1:
                if temp % 2 == 1:
                    code.append("ADD f b")
                    temp = temp - 1
                else:
                    code.append("SHL b")
                    temp = temp // 2
            code.append("ADD b f")

def p_expression_div(p):
     '''
        expression  : value DIV value

     '''
     # div by substraction ? TODO poprawić
     # code.append("( DIV " + str(p[1][1]) + str(p[3][1]) + ' )')
     if p[1][1] == 0 or p[3][1] == 0:
         assign_to_mem(0)
     elif p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] // p[3][1])
     else:
        if p[1][0] != 'num' and p[3][0] != 'num':
            load_var(p[1][1], p[1][2])
            code.append("RESET b")
            code.append("LOAD b a")
            load_var(p[3][1], p[3][2])
            code.append("LOAD a a")
        if p[1][0] == 'num':
            prepare_num(p[1][1], 'b')
            load_var(p[3][1], p[3][2])
            code.append("LOAD a a")
        if p[3][0] == 'num':
            load_var(p[1][1], p[1][2])
            code.append("RESET b")
            code.append("LOAD b a")
            prepare_num(p[3][1], 'a')


        # ALGORITM

        code.append("RESET e")
        code.append("JZERO a 14")
        code.append("INC b")
        code.append("SUB b a")
        code.append("JZERO b 11")
        code.append("ADD b a")
        code.append("DEC b")
        # warunek końca pętli
        code.append("RESET f")
        code.append("ADD f b")
        code.append("INC f")
        code.append("SUB f a")
        # jeżeli a - b = 0 zakończ
        code.append("JZERO f 4")
        code.append("SUB b a")
        code.append("INC e")
        code.append("JUMP -7")
        code.append("RESET b")
        code.append("ADD b e")

def p_expression_mod(p):
     '''
        expression  : value MOD value

     '''
     # code.append("( MOD " + str(p[1][1]) + str(p[3][1]) + ' )')
     if p[1][1] == 0 or p[3][1] == 0:
         assign_to_mem(0)
     elif p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] % p[3][1])
     else:
       if p[1][0] != 'num' and p[3][0] != 'num':
           load_var(p[1][1], p[1][2])
           code.append("RESET b")
           code.append("LOAD b a")
           load_var(p[3][1], p[3][2])
           code.append("LOAD a a")
       if p[1][0] == 'num':
           prepare_num(p[1][1], 'b')
           load_var(p[3][1], p[3][2])
           code.append("LOAD a a")
       if p[3][0] == 'num':
           load_var(p[1][1], p[1][2])
           code.append("RESET b")
           code.append("LOAD b a")
           prepare_num(p[3][1], 'a')

       # ALGORITM
       code.append("JZERO a 14")
       code.append("RESET e")
       code.append("ADD e b")
       code.append("INC e")
       code.append("SUB e a")
       code.append("JZERO e 10")
       code.append("ADD b a")
       # warunek końca pętli
       code.append("RESET f")
       code.append("ADD f b")
       code.append("INC f")
       code.append("SUB f a")
       # jeżeli a - b = 0 zakończ
       code.append("JZERO f 4")
       code.append("SUB b a")
       code.append("JUMP -6")
       code.append("RESET b")

def p_condition_eq(p):
     '''
        condition  :  value EQ value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     code.append("RESET e")
     code.append("ADD e b")
     code.append("SUB e f")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie
     code.append("ADD e f")
     code.append("SUB e b")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie
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
     code.append("RESET e")
     code.append("ADD e b")
     code.append("SUB e f")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     code.append("ADD e f")
     code.append("SUB e b")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_gt(p):
     '''
        condition  : value GT value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     code.append("RESET e")
     code.append("ADD e b")
     code.append("SUB e f")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_lt(p):
     '''
        condition  : value LT value
     '''

     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     code.append("RESET e")
     code.append("ADD e f")
     code.append("SUB e b")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_geq(p):
     '''
        condition  : value GEQ value
     '''
     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     code.append("RESET e")
     code.append("ADD e b")
     code.append("INC e")
     code.append("SUB e f")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie (potencjalne przyspieszenie)
     labels.append(("END", ""))
     p[0] = gen_label()

def p_condition_leq(p):
     '''
        condition  : value LEQ value
     '''
     labels.append((gen_label(), "commands_START"))
     prepare_condition(p[1], 'b')
     prepare_condition(p[3], 'f')
     code.append("RESET e")
     code.append("ADD e f")
     code.append("INC e")
     code.append("SUB e b")
     code.append("JZERO e 2")
     labels.append((gen_label(), "commands_YES"))
     code.append("JUMP x") # <- tak
     labels.append((gen_label(), "commands_NO"))
     code.append("JUMP x") # <- nie (potencjalne przyspieszenie)
     labels.append(("END", ""))
     p[0] = gen_label()

def p_value_num(p):
    '''
       value  : NUMBER
    '''
    p[0] = ('num', p[1], -1)

def p_value_identifier(p):
    '''
       value   : identifier
    '''
    p[0] = p[1]

def p_identifier_pid(p):
    '''
       identifier  : pidentifier
    '''
    check_if_exists(p[1])
    p[0] = ('pid', p[1], -1)

def p_identifier_array(p):
    '''
        identifier  : pidentifier LPAREN NUMBER RPAREN
    '''
    check_if_exists(p[1])
    sym = get_sym(p[1])
    if sym[0] == True:
        if p[3] - sym[1] > sym[2] or p[3] - sym[1] < 0:
            raise Exception("Out of bound!")
        p[0] = ('array', p[1], p[3])
    else:
        raise Exception("Nie tablica!")

def p_identifier_par(p):
    '''
       identifier  : pidentifier LPAREN pidentifier RPAREN
    '''
    check_if_exists(p[1])
    check_if_exists(p[3])
    if get_sym(p[1])[0] == True:
        p[0] = ('array', p[1], p[3])
    else:
        raise Exception("Nie tablica!")


def p_error(p):
    if p != None:
        raise Exception("Syntax error in line: " + str(p.lineno) + ': Unknown: ' + str(p.value))


parser = yacc.yacc()
f=open(sys.argv[1], "r")
parsed = parser.parse(f.read(),tracking=True)
