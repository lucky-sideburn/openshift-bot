import SimpleHTTPServer
import SocketServer
import time
import os

#PORT = int(os.environ['LISTEN_PORT'])
PORT = 8080

Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
Handler.extensions_map.update({
    '.webapp': 'application/x-web-app-manifest+json',
});

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "Serving at port " , PORT
httpd.serve_forever()
