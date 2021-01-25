from ply import lex

ERROR = '\033[91m'

tokens = (
    'DECLARE', 'BEGIN', 'END', 'SEMICOLON',
    'IF', 'THEN', 'ELSE', 'ENDIF',
    'WHILE', 'DO', 'ENDWHILE',
    'REPEAT', 'UNTIL',
    'FOR', 'FROM', 'TO', 'DOWNTO', 'ENDFOR',
    'READ', 'WRITE',
    'NUMBER',
    'ADD', 'SUB', 'MUL', 'DIV', 'MOD',
    'EQ', 'NEQ', 'GEQ', 'LEQ', 'GT', 'LT',
    'ASSIGN',
    'LPAREN', 'RPAREN', 'SEP', 'COLON',
    'pidentifier',
)


t_ADD       = r'\+'
t_SUB       = r'\-'
t_MUL       = r'\*'
t_DIV       = r'\/'
t_MOD       = r'\%'

t_EQ        = r'='
t_NEQ       = r'!='
t_GEQ       = r'>='
t_LEQ        = r'<='
t_GT        = r'>'
t_LT        = r'<'

t_ASSIGN    = r':='

t_LPAREN    = r'\('
t_RPAREN    = r'\)'

t_COLON     = r'\:'
t_SEMICOLON = r'\;'

t_DECLARE   = r'DECLARE'
t_BEGIN     = r'BEGIN'
t_SEP       = r','
t_END       = r'END'

t_IF        = r'IF'
t_THEN      = r'THEN'
t_ELSE      = r'ELSE'
t_ENDIF     = r'ENDIF'

t_WHILE     = r'WHILE'
t_DO        = r'DO'
t_ENDWHILE  = r'ENDWHILE'

t_REPEAT    = r'REPEAT'
t_UNTIL     = r'UNTIL'

t_FOR       = r'FOR'
t_FROM      = r'FROM'
t_TO        = r'TO'
t_DOWNTO    = r'DOWNTO'
t_ENDFOR    = r'ENDFOR'


t_READ      = r'READ'
t_WRITE     = r'WRITE'


def t_pidentifier(t):
    r'[_a-z]+'
    return t

def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise Exception(ERROR + "Nieprawidlowy znak: '%s' "%  t.value[0] + " w linii %d" % t.lineno)


t_ignore = ' \t'
t_ignore_comment = r'\[[^\]]*\]'

lexer = lex.lex()
