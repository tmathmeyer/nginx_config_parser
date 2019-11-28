
import sys
from collections import namedtuple

class TOKEN(object):
  def isA(self, cls):
    return self.__class__ == cls
  def __str__(self):
    return self.__class__.__name__[6:]
  def __repr__(self):
    return str(self)

class TOKEN_STRING(TOKEN, namedtuple('TOKEN_STRING', ['line', 'str'])):
  def __str__(self):
    return f'{self.__class__.__name__[6:]}({self.str})'

class TOKEN_COMMENT(TOKEN, namedtuple('TOKEN_COMMENT', ['line', 'cmt'])):
  def __str__(self):
    return f'{self.__class__.__name__[6:]}({self.cmt})'

class TOKEN_NESTED(TOKEN, namedtuple('TOKEN_NESTED', ['line', 'stream'])):
  def __str__(self):
    return f'NESTED_({self.stream})'

class TOKEN_PROP(TOKEN, namedtuple('TOKEN_PROP', ['line', 'key', 'values'])):
  def __str__(self):
    return f'PROP_({self.key} {self.values})'

class TOKEN_ENTRY(TOKEN, namedtuple('TOKEN_ENTRY', ['line', 'key', 'values'])):
  def __str__(self):
    return f'ENTRY_({self.key} {self.values})'

class TOKEN_NEWLINE(TOKEN, namedtuple('TOKEN_NEWLINE', ['line'])):
  pass

class TOKEN_SEMICOLON(TOKEN, namedtuple('TOKEN_SEMICOLON', ['line'])):
  pass

class TOKEN_OPEN_BRACE(TOKEN, namedtuple('TOKEN_OPEN_BRACE', ['line'])):
  pass

class TOKEN_CLOSE_BRACE(TOKEN, namedtuple('TOKEN_CLOSE_BRACE', ['line'])):
  pass

class TOKEN_OPEN_PAREN(TOKEN, namedtuple('TOKEN_OPEN_PAREN', ['line'])):
  pass

class TOKEN_CLOSE_PAREN(TOKEN, namedtuple('TOKEN_CLOSE_PAREN', ['line'])):
  pass

class TOKEN_OCTOTHORPE(TOKEN, namedtuple('TOKEN_OCTOTHORPE', ['line'])):
  pass



class NginXObject(object):
  def __str__(self):
    return self.ToIndentedString()

  def ParseStream(self, stream, named_entries):
    trailing_comment = []
    self.tags = []
    for token in stream:
      if type(token) == str:
        assert False, f'{token} in {stream}'
      if token.isA(TOKEN_COMMENT):
        trailing_comment.append(token.cmt)
      elif token.isA(TOKEN_PROP):
        self.tags.append(NginXProperty(
          token.key, token.values, ' '.join(trailing_comment)))
        trailing_comment = []
      elif token.isA(TOKEN_ENTRY):
        assert token.key in named_entries.keys(), f'{token.key} not in {named_entries}'
        named_entries[token.key](token.values, ' '.join(trailing_comment))
        trailing_comment = []
      else:
        raise ValueError(str(token))


def chop_comment(comment, spacer, line_length=80):
  remaining_len = line_length - (12 + len(spacer))
  def chop(words, length):
    remlen = length
    line = []
    for word in words:
      if remlen - len(word) > 0:
        line.append(word)
        remlen -= len(word)
      else:
        yield line
        remlen = length - len(word)
        line = [word]
    if line:
      yield line
  def add_thorpe():
    newline=True
    for wordlist in chop(comment.split(), remaining_len):
      newline=False
      yield f'{spacer}# {" ".join(wordlist)}'
    if not newline:
      yield ''
  return '\n'.join(add_thorpe())


def format_properties(props, idt=0, indent='  '):
  has_comments = {}
  no_comments = {}
  for prop in props:
    formatted = prop.ToIndentedString(idt, indent)
    if len(formatted.split('\n')) > 1:
      has_comments[prop.name] = formatted
    else:
      no_comments[prop.name] = formatted

  result = ''
  for key in sorted(has_comments.keys()):
    result += has_comments[key] + '\n\n'

  for key in sorted(no_comments.keys()):
    result += no_comments[key] + '\n'

  return result


class NginXConfig(NginXObject):
  def __init__(self):
    pass

  def RunStream(self, filename):
    stream = self.readfile(filename)
    steps = [
      self._skipSpaces, # STRING, NEWLINE
      self._separateOctothorpes,
      self._renameOctothorpes,
      self._extractComments, # COMMENT
      self._separateSymbols,
      self._renameSemicolons,
      self._renameTerminals,
      self._createNested, # NESTED
      self._typenested, # PROP, ENTRY
    ]
    for step in steps:
      stream = step(stream)
    return stream

  def readfile(self, fname):
    with open(fname, 'r') as f:
      yield from enumerate(f.readlines())

  def _skipSpaces(self, stream):
    for line, chunk in stream:
      for c in chunk.split():
        yield TOKEN_STRING(line+1, c)
      yield TOKEN_NEWLINE(line+1)

  def _separateTokens(self, starts=[], ends=[]):
    def gentake(start=None, end=None):
      def GEN(S):
        for token in S:
          if token.isA(TOKEN_NEWLINE):
            yield token
          elif token.isA(TOKEN_STRING):
            ss = token.str
            while start and ss.startswith(start):
              yield TOKEN_STRING(token.line, start)
              ss = ss[1:]
            ends_cnt = 0
            while end and ss.endswith(end):
              ends_cnt += 1
              ss = ss[:-1]
            if ss:
              yield TOKEN_STRING(token.line, ss)
            for _ in range(ends_cnt):
              yield TOKEN_STRING(token.line, end)
          else:
            yield token
      return GEN

    def gengen(S, G, *gens):
      if not gens:
        yield from G(S)
      else:
        yield from G(gengen(S, *gens))

    def runner(stream):
      tokens = [
        gentake(start=x) for x in starts
      ] + [
        gentake(end=x) for x in ends
      ]
      yield from gengen(stream, *tokens)

    return runner

  def _separateOctothorpes(self, stream):
    return self._separateTokens(starts=['#'])(stream)

  def _separateSymbols(self, stream):
    return self._separateTokens(starts=['{', '('], ends=['}', ')', ';'])(stream)

  def _renameOctothorpes(self, stream):
    return self._nameTokens({'#': TOKEN_OCTOTHORPE})(stream)

  def _renameSemicolons(self, stream):
    return self._nameTokens({';': TOKEN_SEMICOLON})(stream)

  def _renameTerminals(self, stream):
    return self._nameTokens({
      '{': TOKEN_OPEN_BRACE,
      '}': TOKEN_CLOSE_BRACE,
      '(': TOKEN_OPEN_PAREN,
      ')': TOKEN_CLOSE_PAREN,
    })(stream)

  def _nameTokens(self, rename_to):
    def helper(stream):
      for tok in stream:
        if tok.isA(TOKEN_STRING):
          if tok.str in rename_to:
            yield rename_to[tok.str](tok.line)
          else:
            yield tok
        else:
          yield tok
    return helper

  def _extractComments(self, stream):
    comment = None
    stream = iter(stream)
    try:
      while True:
        tok = next(stream)
        if tok.isA(TOKEN_NEWLINE):
          if comment is not None:
            yield TOKEN_COMMENT(tok.line, ' '.join(comment))
            comment = None
          yield tok
        elif tok.isA(TOKEN_OCTOTHORPE):
          if comment is None:
            comment = []
          else:
            comment.append('#')
        elif tok.isA(TOKEN_STRING):
          if comment is not None:
            comment.append(tok.str)
          else:
            yield tok
        else:
          yield tok
    except StopIteration:
      if comment is not None:
        yield TOKEN_COMMENT(' '.join(comment))

  def _createNested(self, stream):
    def _helper(S):
      try:
        while True:
          tok = next(S)
          if tok.isA(TOKEN_OPEN_BRACE):
            yield TOKEN_NESTED(tok.line, list(_helper(S)))
          elif tok.isA(TOKEN_CLOSE_BRACE):
            break
          else:
            yield tok
      except StopIteration:
        pass
    return _helper(iter(stream))

  def _typenested(self, stream):
    def helper(S):
      key = None
      values = []
      for token in S:
        if token.isA(TOKEN_STRING) and (key is None):
          key = token.str
        elif token.isA(TOKEN_STRING) and (key is not None):
          values.append(token.str)
        elif token.isA(TOKEN_NEWLINE):
          # Do nothing on a newline
          pass
        elif token.isA(TOKEN_SEMICOLON):
          assert len(values) > 0, f'Semicolon found with no values in {S}'
          yield TOKEN_PROP(token.line, key, values)
          key = None
          values = []
        elif token.isA(TOKEN_COMMENT):
          yield token
        elif token.isA(TOKEN_OPEN_PAREN):
          assert key == 'if'
          values.append('(')
        elif token.isA(TOKEN_CLOSE_PAREN):
          assert key == 'if'
          values.append(')')
        elif token.isA(TOKEN_NESTED):
          assert key is not None
          values.append(list(helper(token.stream)))
          yield TOKEN_ENTRY(token.line, key, values)
          key = None
          values = []
    yield from helper(stream)

  def ParseFile(self, fname):
    self.ParseStream(self.RunStream(fname), {
      'events': self._ParseEvents,
      'http': self._ParseHTTP
    })

  def _ParseEvents(self, values, comment):
    self.events = NginXEvents(values[0], comment)

  def _ParseHTTP(self, values, comment):
    self.http = NginXHTTP(values[0], comment)

  def ToIndentedString(self, idt=0, indent='  '):
    assert idt == 0, 'Cant call ToIndentedString on NginXConfig an indent'
    tags = format_properties(self.tags)
    events = self.events.ToIndentedString(idt, indent)
    http = self.http.ToIndentedString(idt, indent)
    return f'{tags}\n{events}\n\n{http}'


class NginXBracedObject(NginXObject):
  def ToIndentedString(self, idt=0, indent='  '):
    indentation = indent * idt
    result = f'{indentation}{self.GetBraceName()}{{'
    for i in self.StringifyEachEntry(idt+1, indent):
      result += f'\n{i}'
    result += f'\n{indentation}}}'
    return result

  def StringifyEachEntry(self, idt, indent):
    raise ValueError(
      f'StringifyEachEntry unimplemented on {self.__class__.__name__}')

  def GetBraceName(self):
    raise ValueError(
      f'GetBraceName unimplemented on {self.__class__.__name__}')


class NginXProperty(object):
  def __init__(self, name, value, comment=''):
    self.name = name
    self.value = ' '.join(value)
    self.comment = comment

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    result = ''
    comment = chop_comment(self.comment, spacer)
    result += f'{comment}{spacer}{self.name} {self.value};'
    return result


class NginXEvents(NginXBracedObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.ParseStream(values, {})

  def StringifyEachEntry(self, idt, indent):
    indentation = indent * idt
    comment = chop_comment(self.comment, indentation)
    if comment:
      yield comment
    for tag in self.tags:
      yield tag.ToIndentedString(idt, indent)

  def GetBraceName(self):
    return 'events '


class NginXHTTP(NginXBracedObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.servers = []
    self.upstreams = []
    self.ParseStream(values, {
      'server': self._ParseServer,
      'upstream': self._ParseUpstream,
    })

  def StringifyEachEntry(self, idt, indent):
    indentation = indent * idt
    comment = chop_comment(self.comment, indentation)
    if comment:
      yield comment
    for tag in self.tags:
      yield tag.ToIndentedString(idt, indent)
    for server in self.servers:
      yield ''  # put a newline after each server block
      yield server.ToIndentedString(idt, indent)
    for upstream in self.upstreams:
      yield ''  # put a newline after each server block
      yield upstream.ToIndentedString(idt, indent)

  def GetBraceName(self):
    return 'http '

  def _ParseServer(self, values, comment):
    self.servers.append(NginXServer(values[0], comment))

  def _ParseUpstream(self, values, comment):
    print(values)


class NginXServer(NginXBracedObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.locations = []
    self.conditions = []
    self.ParseStream(values, {
      'location': self._ParseLocation,
      'if': self._ParseIf,
    })

  def StringifyEachEntry(self, idt, indent):
    indentation = indent * idt
    comment = chop_comment(self.comment, indentation)
    if comment:
      yield comment
    for tag in self.tags:
      yield tag.ToIndentedString(idt, indent)
    for location in self.locations:
      yield ''
      yield location.ToIndentedString(idt, indent)
    for condition in self.conditions:
      yield ''  # put a newline after each condition
      yield condition.ToIndentedString(idt, indent)

  def GetBraceName(self):
    return 'server '

  def _ParseLocation(self, values, comment):
    self.locations.append(NginXLocation(values[:-1], values[-1], comment))

  def _ParseIf(self, values, comment):
    self.conditions.append(NginXCondition(values, comment))


class NginXLocation(NginXBracedObject):
  def __init__(self, location, values, comment=''):
    self.comment = comment
    self.location = ' '.join(location)
    self.conditions = []
    self.ParseStream(values, {
      'if': self._ParseIf
    })

  def StringifyEachEntry(self, idt, indent):
    indentation = indent * idt
    comment = chop_comment(self.comment, indentation)
    if comment:
      yield comment
    for tag in self.tags:
      yield tag.ToIndentedString(idt, indent)

  def GetBraceName(self):
    return f'location {self.location} '

  def _ParseIf(self, values, comment):
    self.conditions.append(NginXCondition(values, comment))


class NginXCondition(NginXBracedObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.condition_string = []
    self.body = None
    self._parseTokens(values)

  def _parseTokens(self, values):
    self.ParseStream(values[-1], {})
    self.condition_string = values[1:-2]

  def StringifyEachEntry(self, idt, indent):
    indentation = indent * idt
    comment = chop_comment(self.comment, indentation)
    if comment:
      yield comment
    for tag in self.tags:
      yield tag.ToIndentedString(idt, indent)

  def GetBraceName(self):
    condition = ' '.join(self.condition_string)
    return f'if ({condition}) '
