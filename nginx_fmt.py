
import sys

from nginxweb import nginxio

def main():
  config = nginxio.NginXConfig()
  config.ParseFile(sys.argv[1])
  print(config)