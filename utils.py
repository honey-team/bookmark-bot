from typing import *

import time
import random


# functions

def str_to_superscript(string:str) -> str:
    '''
    Converts a string to a string with superscript letters.
    '''
    string = str(string)
    replace_from = 'ABDEGHIJKLMNOPRTUVWabcdefghijklmnoprstuvwxyz+-=()0123456789.'
    replace_to =   'ᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁺⁻⁼⁽⁾⁰¹²³⁴⁵⁶⁷⁸⁹·'

    for a, b in list(zip(replace_from, replace_to)):
        string = string.replace(a,b)
        
    return string
    

def remove_md(string:str, escape_spoilers:bool=False) -> str:
    '''
    Escapes any markdown symbols.
    '''
    string = string.replace('\\', '\\\\') # confusing af 
    string = string.replace('*', '\\*')
    string = string.replace('_', '\\_')
    string = string.replace('~', '\\~')
    if escape_spoilers:
        string = string.replace('|', '\\|')

    return string

    
def shorten_string(string:str, max_chars:int=50, remove_newlines:bool=True) -> str:
    '''
    Strips the string.
    '''
    dots = False
    
    if len(string) > max_chars:
        dots = True
        string = string[:max_chars-3]
    
    if remove_newlines and '\n' in string:
        dots = True
        string = string.split('\n')[0]

    return string+('...' if dots else '')

    
def rand_id(k:int=4) -> str:
    '''
    Generates a random unique (probably) hexadecimal string that can be used as an ID.
    '''
    timestamp = str(int(time.time())) # unique timestamp that changes every second and never repeats after
    random_part = "".join(random.choices('0123456789', k=k)) # randomly generated string to add
                                                             # after the timestamp
    string = hex(int(timestamp+random_part))[2:] # converting the number to hex to make it shorter
    return string
