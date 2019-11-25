
import sys
from collections import namedtuple

class TOKEN(object):
  def isA(self, cls):
    return self.__class__ == cls
  def __str__(self):
    return self.__class__.__name__[6:]
  def __repr__(self):
    return str(self)

class TOKEN_STRING(TOKEN, namedtuple('TOKEN_STRING', ['str'])):
  def __str__(self):
    return f'{self.__class__.__name__[6:]}({self.str})'

class TOKEN_COMMENT(TOKEN, namedtuple('TOKEN_COMMENT', ['cmt'])):
  def __str__(self):
    return f'{self.__class__.__name__[6:]}({self.cmt})'

class TOKEN_NESTED(TOKEN, namedtuple('TOKEN_NESTED', ['stream'])):
  pass

class TOKEN_PROP(TOKEN, namedtuple('TOKEN_PROP', ['key', 'values'])):
  pass

class TOKEN_ENTRY(TOKEN, namedtuple('TOKEN_ENTRY', ['key', 'values'])):
  pass

class TOKEN_NEWLINE(TOKEN):
  pass

class TOKEN_SEMICOLON(TOKEN):
  pass

class TOKEN_OPEN_BRACE(TOKEN):
  pass

class TOKEN_CLOSE_BRACE(TOKEN):
  pass

class TOKEN_OCTOTHORPE(TOKEN):
  pass



class NginXObject(object):
  def ParseStream(self, stream, named_entries):
    trailing_comment = []
    self.tags = []
    for token in stream:
      if token.isA(TOKEN_COMMENT):
        trailing_comment.append(token.cmt)
      elif token.isA(TOKEN_PROP):
        self.tags.append(NginXProperty(
          token.key, token.values[0], ' '.join(trailing_comment)))
        trailing_comment = []
      elif token.isA(TOKEN_ENTRY):
        if token.key in named_entries.keys():
          named_entries[token.key](token.values, ' '.join(trailing_comment))
        else:
          raise ValueError(str(token) + '  ' + str(token.key))
        trailing_comment = []
      else:
        raise ValueError(str(token))



class NginXFileIO(NginXObject):
  def __init__(self):
    pass

  def readfile(self, fname):
    with open(fname, 'r') as f:
      return f.readlines()

  def _skipSpaces(self, fname): # -> [STRING, NEWLINE]
    for chunk in self.readfile(fname):
      for c in chunk.split():
        yield TOKEN_STRING(c)
      yield TOKEN_NEWLINE()

  def _sepTokens(self, fname):
    def gentake(start=None, end=None):
      def GEN(stream):
        for token in stream:
          if token.isA(TOKEN_NEWLINE):
            yield token
          if token.isA(TOKEN_STRING):
            ss = token.str
            while start and ss.startswith(start):
              yield TOKEN_STRING(start)
              ss = ss[1:]
            ends_cnt = 0
            while end and ss.endswith(end):
              ends_cnt += 1
              ss = ss[:-1]
            if ss:
              yield TOKEN_STRING(ss)
            for _ in range(ends_cnt):
              yield TOKEN_STRING(end)
      return GEN

    def gengen(stream, G, *gens):
      if not gens:
        yield from G(stream)
      else:
        yield from G(gengen(stream, *gens))

    yield from gengen(self._skipSpaces(fname),
      gentake(start='#'),
      gentake(start='{'),
      gentake(end='}'),
      gentake(end=';'))

  def _nameTokens(self, fname):
    for tok in self._sepTokens(fname):
      if tok.isA(TOKEN_STRING):
        if tok.str == '{':
          yield TOKEN_OPEN_BRACE()
        elif tok.str == '}':
          yield TOKEN_CLOSE_BRACE()
        elif tok.str == '#':
          yield TOKEN_OCTOTHORPE()
        elif tok.str == ';':
          yield TOKEN_SEMICOLON()
        else:
          yield tok
      else:
        yield tok

  def _extractComments(self, fname):
    comment = None
    stream = self._nameTokens(fname)
    try:
      while True:
        tok = next(stream)
        if tok.isA(TOKEN_NEWLINE):
          if comment is not None:
            yield TOKEN_COMMENT(' '.join(comment))
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

  def _createNested(self, fname):
    def _helper(stream):
      try:
        while True:
          tok = next(stream)
          if tok.isA(TOKEN_OPEN_BRACE):
            yield TOKEN_NESTED(list(_helper(stream)))
          elif tok.isA(TOKEN_CLOSE_BRACE):
            break
          else:
            yield tok
      except StopIteration:
        pass
    return _helper(self._extractComments(fname))

  def _typenested(self, fname):
    def helper(stream):
      key = None
      values = []
      for token in stream:
        if token.isA(TOKEN_STRING) and (key is None):
          key = token.str
        elif token.isA(TOKEN_STRING) and (key is not None):
          values.append(token.str)
        elif token.isA(TOKEN_NEWLINE):
          assert key is None
        elif token.isA(TOKEN_SEMICOLON):
          assert len(values) > 0
          yield TOKEN_PROP(key, values)
          key = None
          values = []
        elif token.isA(TOKEN_COMMENT):
          yield token
        elif token.isA(TOKEN_NESTED):
          assert key is not None
          values.append(list(helper(token.stream)))
          yield TOKEN_ENTRY(key, values)
          key = None
          values = []
    yield from helper(self._createNested(fname))

  def ParseFile(self, fname):
    self.ParseStream(self._typenested(fname), {
      'events': self._ParseEvents,
      'http': self._ParseHTTP
    })

  def _ParseEvents(self, values, comment):
    self.events = NginXEvents(values[0], comment)

  def _ParseHTTP(self, values, comment):
    self.http = NginXHTTP(values[0], comment)

  def __str__(self):
    tags = format_properties(self.tags)
    events = self.events.ToIndentedString()
    http = self.http.ToIndentedString()

    return f'{tags}\n{events}{http}'


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
        remlen = length
        line = []
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




class NginXProperty(object):
  def __init__(self, name, value, comment=''):
    self.name = name
    self.value = value
    self.comment = comment

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    result = ''
    comment = chop_comment(self.comment, spacer)
    result += f'{comment}{spacer}{self.name} {self.value};'
    return result


class NginXEvents(NginXObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.ParseStream(values, {})

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    tags = format_properties(self.tags, idt+1)
    comment = chop_comment(self.comment, spacer)
    return f'{comment}{spacer}events {{\n{tags}{spacer}}}\n\n'


class NginXHTTP(NginXObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.servers = []
    self.ParseStream(values, {
      'server': self._ParseServer
    })

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    tags = format_properties(self.tags, idt+1)
    servers = '\n'.join(s.ToIndentedString(idt+1) for s in self.servers)
    comment = chop_comment(self.comment, spacer)
    return f'{comment}{spacer}http {{\n{tags}\n{servers}{spacer}}}\n\n'

  def _ParseServer(self, values, comment):
    self.servers.append(NginXServer(values[0], comment))


class NginXServer(NginXObject):
  def __init__(self, values, comment=''):
    self.comment = comment
    self.location = None
    self.ParseStream(values, {
      'location': self._ParseLocation,
      'if': self._ParseIf,
    })

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    tags = format_properties(self.tags, idt+1)
    comment = chop_comment(self.comment, spacer)
    location = '' 
    if self.location:
      location = '\n' + self.location.ToIndentedString(idt+1)
    return f'{comment}{spacer}server {{\n{tags}{location}{spacer}}}\n'

  def _ParseLocation(self, values, comment):
    self.location = NginXLocation(values[0], values[1], comment)

  def _ParseIf(self, values, comment):
    print(values, comment)


class NginXLocation(NginXObject):
  def __init__(self, location, values, comment=''):
    self.comment = comment
    self.location = location
    self.ParseStream(values, {})

  def ToIndentedString(self, idt=0, indent='  '):
    spacer = indent * idt
    tags = format_properties(self.tags, idt+1)
    comment = chop_comment(self.comment, spacer)
    return f'{comment}{spacer}location {self.location} {{\n{tags}{spacer}}}\n'






def main():
  x = NginXFileIO()
  x.ParseFile(sys.argv[1])
  print(x)
  

