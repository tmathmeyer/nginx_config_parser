langs("Python")

py_library(
  name="nginxio",
  srcs=[ "nginxio.py" ],
)

py_binary(
  name = "nginx_fmt",
  srcs = [ "nginx_fmt.py" ],
  deps = [ ":nginxio"]
)

py_binary(
  name = "nginx_fmt_debug",
  srcs = [ "nginx_fmt_debug.py" ],
  deps = [ ":nginxio"]
)