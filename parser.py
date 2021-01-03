from ply import yacc
import sys
import lexer

tokens = lexer.tokens

# symbol table: (name) or (name, tab_start, tab_end)
sym_tab = {}
data_offset = 0
# for -> for_jmp
labels = []
code_offset = 0
code = []

def add_to_sym_tab(sym_name, is_tab, t_start, t_itr, offset):
    # print(sym_name," ",is_tab)
    if sym_name not in sym_tab:
        sym_tab.update({sym_name: [is_tab, t_start, t_itr, offset]})
    else:
        raise Exception("%s already defined!", sym_name)

def get_sym(sym_name):
    return sym_tab[sym_name]

def check_if_exists(sym_name):
    if sym_name not in sym_tab:
        raise Exception("%s is undeclared", sym_name)

def check_if_init(sym_name):
    if get_sym(sym_name)[4] == -1:
        raise Exception("%s is not initialized", sym_name)


def data_location():
    global data_offset
    data_offset += 1
    return data_offset

def gen_label():
    return code_offset

def reserve_loc():
    global code_offset
    code_offset +=1
    return code_offset


def gen_code(operation, args):
    global code
    opp = operation
    for arg in args:
        operation += str(arg)
    code.append(opp)

def back_path(addr, operation, args):
    global code
    opp = operation
    for arg in args:
        operation += str(arg)
    code[addr] = opp



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

            if itr < 0 or itr > sym[2]:
                raise Exception("Index out of bounds in table: " + sym_name)

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

                if itr < 0 or itr > sym[2]:
                    raise Exception("Index out of bounds in table: " + sym_name)

                prepare_num(itr, 'a')
            else:   # tab(pid)
                assign_to_tab(sym_name, arr, 'a')

        code.append("LOAD b a")


def math_opperation(arg_1, arg_2, opp):
    code.append("( " + opp + str(arg_1[1]) + " " + str(arg_2[1]) + ' )')
    if arg_1[0] == 'num':
        prepare_num(arg_1[1], 'b')
        load_var(arg_2[1], arg_2[2])
        code.append("LOAD a a")
        code.append(opp + "b a")

    if arg_2[0] == 'num':
        prepare_num(arg_2[1], 'b')
        load_var(arg_1[1], arg_1[2])
        code.append("LOAD a a")
        code.append(opp + "b a")

    if arg_1[0] != 'num' and arg_2[0] != 'num':
        load_var(arg_1[1], arg_1[2])
        code.append("RESET e")
        code.append("LOAD e a")
        load_var(arg_2[1], arg_2[2])
        code.append("RESET b")
        code.append("LOAD b a")
        code.append(opp + "b e")



precedence = (

    ('left', 'ADD', 'SUB'),
    ('left', 'MUL', 'DIV', 'MOD'),
    ('nonassoc', 'EQ', 'NEQ', 'GT', 'LT', 'GEQ', 'LEQ'),

)

def print_memory():
    global data_offset
    code.append("RESET a")
    for _ in range(data_offset + 1):
        code.append("PUT a")
        code.append("INC a")

def p_program(p):
    '''
        program     : DECLARE declarations BEGIN commands END
                    | BEGIN commands END

    '''
    # print_memory()
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
    add_to_sym_tab(p[1], True, p[3], p[5] - p[3], data_location())
    data_offset += p[5] - p[3]

def p_commands(p):
    '''
        commands         : commands command
                         | command
    '''

def p_command_assign(p):
    '''
        command         : identifier ASSIGN expression SEMICOLON
    '''
    if p[1][0] == 'num':
        raise Exception("Nieprawidłowe przypisanie!")

    code.append("( Init " + str(p[1][1]) +  ' )')
    # assign_to_mem(p[3][1], p[3][2])
    load_var(p[1][1], p[1][2])
    code.append("STORE b a")

def p_command_assign_read(p):
    '''
        command         : READ identifier SEMICOLON
    '''
    off = get_sym(p[2][1])[3]
    code.append("RESET a")
    prepare_num(off, 'a', False)
    code.append("GET a")

def p_command(p):
    '''
        command         :  IF condition THEN commands ELSE commands ENDIF
                         | IF condition THEN commands ENDIF
                         | WHILE condition DO commands ENDWHILE
                         | REPEAT commands UNTIL condition SEMICOLON
                         | FOR pidentifier FROM value TO value DO commands ENDFOR
                         | FOR pidentifier FROM value DOWNTO value DO commands ENDFOR

    '''

def p_command_write(p):
    '''
        command         :   WRITE value SEMICOLON
    '''

    code.append("( Write " + str(p[2][1]) + str(p[2][2]) + ' )')
    sym = get_sym(p[2][1])
    if p[2][0] == 'num':
        # code.append("RESET a")
        prepare_num(p[2][1], 'a', False)
        code.append("PUT a")

    elif p[2][0] == 'pid':
        # code.append("RESET a")
        prepare_num(sym[3], 'a', False)
        code.append("PUT a")
    elif p[2][0] == 'array':
        # TODO write p(a)
        # code.append("RESET a")
        increment = p[2][2] - sym[1] + sym[3]
        prepare_num(increment, 'a', False)
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
        assign_to_mem(p[1][1] - p[3][1])
     else:
         math_opperation(p[1], p[3], "SUB ")


def p_expression_mul(p):
    '''
        expression  : value MUL value
    '''
    if p[1][0] == 'num' and p[3][0] == 'num':
       assign_to_mem(p[1][1] * p[3][1])
    # if not p[1].isdigit()
    #     pass
    # if not p[3].isdigit()
    #     pass
    #
    # a, b = p[1], p[3]
    # if b > a:
    #     a, b = b, a
    #
    # # SHL a , b//2
    # if b % 2 == 1:
    #     while b != 1:
    #         code.append("")





def p_expression_div(p):
     '''
        expression  : value DIV value

     '''

     if p[1][0] == 'num' and p[3][0] == 'num':
        assign_to_mem(p[1][1] // p[3][1])

def p_expression_mod(p):
     '''
        expression  : value MOD value

     '''
      if p[1][0] == 'num' and p[3][0] == 'num':
         assign_to_mem(p[1][1] % p[3][1])


def p_condition(p):
     '''
        condition  :  value EQ value
                    | value NEQ value
                    | value GT value
                    | value LT value
                    | value GEQ value
                    | value LEQ value
     '''

     print(p[1])

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
