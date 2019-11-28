
import sys

from nginxweb import nginxio

BLACK  = '0'
RED    = '1'
GREEN  = '2'
YELLOW = '3'
PURPLE = '5'

def Color(fg=None, bg=None):
  if fg and bg:
    return f'\033[3{fg};4{bg}m'
  if fg:
    return f'\033[3{fg}m'
  if bg:
    return f'\033[4{bg}m'
  return '\033[0m'

def highlightStream(stream, highlights):
  result = ''
  for entry in stream:
    add = str(entry)
    for h in highlights:
      if add.startswith(h):
        add = f'{Color(RED)}{h}{Color()}{add[len(h):]}{Color()}'
    result += add + ' '
  return result

def main():
  config = nginxio.NginXConfig()
  stream = list(config.readfile(sys.argv[1]))
  highlight = []
  steps = {
    config._skipSpaces: ['STRING', 'NEWLINE'],
    config._separateOctothorpes: ['STRING(#)'],
    config._renameOctothorpes: ['OCTOTHORPE'],
    config._extractComments: ['COMMENT'],
    config._separateSymbols: ['STRING({)', 'STRING(()', 'STRING(})', 'STRING())'],
    config._renameSemicolons: ['SEMICOLON'],
    config._renameTerminals: ['OPEN_BRACE', 'OPEN_PAREN', 'CLOSE_BRACE', 'CLOSE_PAREN'],
    config._createNested: ['NESTED'], # NESTED
    config._typenested: ['PROP_', 'ENTRY_'], # PROP, ENTRY
  }
  for step, newhighlight in steps.items():
    print(highlightStream(stream, highlight))
    highlight = newhighlight
    print(f'Press [Enter] to run {Color(GREEN)}{step}{Color()} on the previous stream')
    x = input()
    stream = list(step(stream))
  print(highlightStream(stream, highlight))