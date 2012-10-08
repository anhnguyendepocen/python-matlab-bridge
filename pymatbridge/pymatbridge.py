"""
pymatbridge
===========

This is a module for communicating and running 

Part of Python-MATLAB-bridge, Max Jaderberg 2012 

"""

import numpy as np
from httplib import BadStatusLine
import urllib2, urllib, os, json, time
from multiprocessing import Process

MATLAB_FOLDER = '%s/matlab' % os.path.realpath(os.path.dirname(__file__))

class Matlab(object):
    """
    A class for communicating with a matlab session
    """        
    running = False
    matlab = None
    host = None
    port = None
    server = None
    id = None
    server_process = Process()

    def __init__(self, matlab='/Applications/MATLAB_R2011a.app/bin/matlab',
                 host='localhost', port=4000, id='python-matlab-bridge'):
        """
        Initialize this thing
        """

        self.feval = 'web_feval.m'
        self.eval = 'web_eval.m'
            
        self.matlab = matlab
        self.host = host
        self.port = port
        self.server = 'http://%s:%s' % (self.host, str(self.port))
        self.id = id

    def start(self):
        def _run_matlab_server():
            os.system('%s -nodesktop -nosplash -r "cd pymatbridge/matlab,webserver(%s),exit" -logfile ./pymatbridge/logs/matlablog_%s.txt > ./pymatbridge/logs/bashlog_%s.txt' % (self.matlab, self.port, self.id, self.id))
            return True
        # Start the MATLAB server
        print "Starting MATLAB"
        self.server_process = Process(target=_run_matlab_server)
        self.server_process.daemon = True
        self.server_process.start()
        while not self.is_connected():
            np.disp(".", linefeed=False)
            time.sleep(1)
        print "MATLAB started and connected!"
        return True



    def stop(self):
        # Stop the MATLAB server
        try:
            try:
                resp = self._open_page('exit_server.m', {'id': self.id})
            except BadStatusLine:
                pass
        except urllib2.URLError:
            pass
        print "MATLAB closed"
        return True

    def is_connected(self):
        try:
            resp = self._open_page('test_connect.m', {'id': self.id})
            if resp['message']:
                return True
        except urllib2.URLError:
            pass
        return False

    def is_function_processor_working(self):
        try:
            result = self.run_func('%s/test_functions/test_sum.m' % MATLAB_FOLDER, {'echo': 'Matlab: Function processor is working!'})
            if result['success'] == 'true':
                return True
        except urllib2.URLError:
            pass
        return False

    def run_func(self, func_path, func_args=None, maxtime=None):
        if self.running:
            time.sleep(0.5)
        page_args = {
            'func_path': func_path,
        }
        if func_args:
            page_args['arguments'] = json.dumps(func_args)
        if maxtime:
            result = self._open_page(self.feval, page_args, maxtime)
        else:
            result = self._open_page(self.feval, page_args)
        return result


    def run_code(self, code, maxtime=None):
        """

        Run a piece of code provided as a string

        """
        if self.running:
            time.sleep(0.5)
            
        if maxtime:
            result = self._open_page(self.eval, dict(code=code), maxtime)
        else:
            result = self._open_page(self.eval, dict(code=code))

        return result
        

        
    def _open_page(self, page_name, arguments={}, timeout=10):
        self.running = True
        page = urllib2.urlopen('%s/%s' % (self.server, page_name),
                               urllib.urlencode(arguments),
                               timeout)
        
        self.running = False
        read_page = page.read()
        # Deal with escape characters: json needs an additional '\': 
        return json.loads(read_page.replace("\n","\\n"))


