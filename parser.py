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
    code.append("RESET " + register)
    prepare_num(arr_off, register, False)
    code.append("RESET e")
    code.append("LOAD " + 'e' + " " + register)
    # biorę p(a)
    code.append("RESET " + register)
    # jestem na p(0)
    prepare_num(off - start, register, False)
    # jestem na p(arr)
    code.append("ADD " + register + " " + 'e')


def prepare_assign(name_A, name_B, tab_A_mem=0, tab_B_mem=0):

    if name_B[0] != 'expression':
        # p(b) =
        skip_A = False
        # = p(b)
        skip_B = False
        sym_A = get_sym(name_A)
        sym_B = get_sym(name_B)

        if str(tab_A_mem).isdigit() == False:
            skip_A = True

        if str(tab_B_mem).isdigit() == False:
            skip_B = True

        if skip_A == False:
            itr_A = sym_A[3] + (tab_A_mem - sym_A[1])
            if sym_A[0] == True:
                if itr_A < 0 or tab_A_mem > sym_A[2]:
                    raise Exception("Index out of bounds in table: " + name_A)

        if skip_B == False:
            itr_B = sym_B[3] + (tab_B_mem - sym_B[1])
            if sym_B[0] == True:
                if itr_B < 0 or tab_B_mem > sym_B[2]:
                    raise Exception("Index out of bounds in table: " + name_B)


        if skip_B == False:
            code.append("RESET a")

        code.append("( Init " + name_A + "=" + name_B + ' )')

        if skip_B == False:
            prepare_num(itr_B, 'a', False)
        else:
            assign_to_tab(name_B, tab_B_mem, 'a')
        code.append("RESET b")
        code.append("LOAD b a")
        if skip_A == False:
            code.append("RESET a")
            prepare_num(itr_A, 'a', False)
        else:
            assign_to_tab(name_A, tab_A_mem, 'a')
        code.append("STORE b a")
    else:
        sym_A = get_sym(name_A)
        skip_A = False
        if str(tab_A_mem).isdigit() == False:
            skip_A = True

        if skip_A == False:
            itr_A = sym_A[3] + (tab_A_mem - sym_A[1])
            if sym_A[0] == True:
                if itr_A < 0 or tab_A_mem > sym_A[2]:
                    raise Exception("Index out of bounds in table: " + name_A)

        code.append("( Init " + name_A + "=" + 'expression' + ' )')
        code.append(name_B[1])
        if skip_A == False:
            code.append("RESET a")
            prepare_num(itr_A, 'a', False)
        else:
            assign_to_tab(name_A, tab_A_mem, 'a')

        code.append("STORE b a")




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
    print(p[3])
    if p[1][0] == 'num':
        raise Exception("Nieprawidłowe przypisanie!")
    if p[1][0] == 'pid':
        if p[3][0] == 'num':
            code.append("( Init " + p[1][1] + "=" + str(p[3][1]) + ' )')
            code.append("RESET a")
            off = get_sym(p[1][1])[3]
            prepare_num(off, 'a', False)
            code.append("RESET b")
            prepare_num(p[3][1], 'b', False)
            code.append("STORE b a")
            code.append("RESET b")
        elif if p[3][0] == 'expression':
            pass
        else:
            prepare_assign(p[1][1], p[3][1], tab_B_mem=p[3][2])


    elif p[1][0] == 'array':
        if p[3][0] == 'num':
            code.append("( Init " + p[1][1] + "=" + str(p[3][1]) + ' )')
            code.append("RESET a")
            off = get_sym(p[1][1])[3] + (p[1][2] - get_sym(p[1][1])[1])

            prepare_num(off, 'a', False)
            code.append("RESET b")
            prepare_num(p[3][1], 'b', False)
            code.append("STORE b a")
            code.append("RESET b")
        elif if p[3][0] == 'expression':
            pass
        else:
            prepare_assign(p[1][1], p[3][1], tab_A_mem=p[1][2], tab_B_mem=p[3][2])


def p_command_assign_read(p):
    '''
        command         : READ identifier SEMICOLON
    '''
    off = get_sym(p[2][0])[3]

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
        code.append("RESET a")
        prepare_num(p[2][1], 'a', False)
        code.append("PUT a")

    elif p[2][0] == 'pid':
        code.append("RESET a")
        prepare_num(sym[3], 'a', False)
        code.append("PUT a")
    elif p[2][0] == 'array':
        # TODO write p(a)
        code.append("RESET a")
        increment = p[2][2] - sym[1] + sym[3]
        prepare_num(increment, 'a', False)
        code.append("PUT a")

def p_expression_value(p):
     '''
        expression  : value

     '''
     p[0] = p[1]

def p_expression_add(p):
     '''
        expression  : value ADD value
     '''
     # code.append("ADD a")
     if p[1][0] == 'num' and p[3][0] == 'num':
         p[0] = ('num', p[1][1] + p[3][1])


def p_expression_sub(p):
     '''
        expression  : value SUB value

     '''
     code.append("SUB a")
     p[0] = p[1] - p[3]

def p_expression_mul(p):
    '''
        expression  : value MUL value
    '''
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

def p_expression_mod(p):
     '''
        expression  : value MOD value

     '''


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
    p[0] = ('num', p[1])
    # prepare_num(p[1], 'a')

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
    p[0] = ('pid', p[1], 0)

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
        # check_if_init(p[3])
        #here prepre
        p[0] = ('array', p[1], p[3])
    else:
        raise Exception("Nie tablica!")


def p_error(p):
    if p != None:
        raise Exception("Syntax error in line: " + str(p.lineno) + ': Unknown: ' + str(p.value))


parser = yacc.yacc()
f=open(sys.argv[1], "r")
parsed = parser.parse(f.read(),tracking=True)
