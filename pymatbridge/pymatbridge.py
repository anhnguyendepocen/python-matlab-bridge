"""
pymatbridge
===========

This is a module for communicating and running

Part of Python-MATLAB-bridge, Max Jaderberg 2012

This is a modified version using ZMQ, Haoxing Zhang Jan.2014
"""

import os, time
import zmq
import subprocess
import sys
import json

# JSON encoder extension to handle complex numbers
class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, complex):
            return {'real':obj.real, 'imag':obj.imag}
        # Handle the default case
        return json.JSONEncoder.default(self, obj)

# JSON decoder for complex numbers
def as_complex(dct):
    if 'real' in dct and 'imag' in dct:
        return complex(dct['real'], dct['imag'])
    return dct

MATLAB_FOLDER = '%s/matlab' % os.path.realpath(os.path.dirname(__file__))


class Session(object):
    """
    A class for communicating with a MATLAB session. It provides the behavior
    common across different MATLAB implementations. You shouldn't instantiate
    this directly; rather, use the Matlab or Octave subclasses.
    """

    def __init__(self, executable, socket_addr=None,
                 id='python-matlab-bridge', log=False, maxtime=60,
                 platform=None, startup_options=None):

        self.started = False
        self.running = False
        self.executable = executable
        self.socket_addr = socket_addr
        self.id = id
        self.log = log
        self.maxtime = maxtime
        self.platform = platform if platform is not None else sys.platform
        self.startup_options = startup_options

        if socket_addr is None:
            self.socket_addr = "tcp://127.0.0.1:55555" if self.platform == "win32" else "ipc:///tmp/pymatbridge"

        if self.log:
            startup_options += ' > ./pymatbridge/logs/bashlog_%s.txt' % self.id

        self.context = None
        self.socket = None

    def _preamble_code(self):
        return ["addpath(genpath('%s'))" % MATLAB_FOLDER]

    def _execute_flag(self):
        raise NotImplemented

    def _run_server(self):
        code = self._preamble_code()
        code.extend([
            "matlabserver('%s')" % self.socket_addr,
            'exit'
        ])
        command = '%s %s %s "%s"' % (self.executable, self.startup_options,
                                     self._execute_flag(), ','.join(code))
        subprocess.Popen(command, shell=True, stdin=subprocess.PIPE)

    # Start server/client session and make the connection
    def start(self):
        # Start the MATLAB server in a new process
        print "Starting MATLAB on ZMQ socket %s" % (self.socket_addr)
        print "Send 'exit' command to kill the server"
        self._run_server()

        # Start the client
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.socket_addr)

        self.started = True

        # Test if connection is established
        if self.is_connected():
            print "MATLAB started and connected!"
            return True
        else:
            print "MATLAB failed to start"
            return False

    def _response(self, **kwargs):
        req = json.dumps(kwargs, cls=ComplexEncoder)
        self.socket.send(req)
        resp = self.socket.recv_string()
        return resp

    # Stop the Matlab server
    def stop(self):
        # Matlab should respond with "exit" if successful
        if self._response(cmd='exit') == "exit":
            print "MATLAB closed"

        self.started = False
        return True

    # To test if the client can talk to the server
    def is_connected(self):
        if not self.started:
            time.sleep(2)
            return False

        req = json.dumps(dict(cmd="connect"), cls=ComplexEncoder)
        self.socket.send(req)

        start_time = time.time()
        while True:
            try:
                resp = self.socket.recv_string(flags=zmq.NOBLOCK)
                return resp == "connected"
            except zmq.ZMQError:
                sys.stdout.write('.')
                time.sleep(1)
                if time.time() - start_time > self.maxtime:
                    print "Matlab session timed out after %d seconds" % self.maxtime
                    return False

    def is_function_processor_working(self):
        result = self.run_func('%s/test_functions/test_sum.m' % MATLAB_FOLDER, {'echo': 'Matlab: Function processor is working!'})
        return result['success'] == 'true'

    def _json_response(self, **kwargs):
        if self.running:
            time.sleep(0.05)
        return json.loads(self._response(**kwargs), object_hook=as_complex)

    # Run a function in Matlab and return the result
    def run_func(self, func_path, func_args=None):
        return self._json_response(cmd='run_function',
                                   func_path=func_path,
                                   func_args=func_args)

    # Run some code in Matlab command line provide by a string
    def run_code(self, code):
        return self._json_response(cmd='run_code', code=code)

    def get_variable(self, varname):
        return self._json_response(cmd='get_var', varname=varname)['var']


class Matlab(Session):
    def __init__(self, executable='matlab', socket_addr=None,
                 id='python-matlab-bridge', log=False, maxtime=60,
                 platform=None, startup_options=None):
        """
        Initialize this thing.

        Parameters
        ----------

        executable : str
            A string that would start Matlab at the terminal. Per default, this
            is set to 'matlab', so that you can alias in your bash setup

        socket_addr : str
            A string that represents a valid ZMQ socket address, such as
            "ipc:///tmp/pymatbridge", "tcp://127.0.0.1:55555", etc.

        id : str
            An identifier for this instance of the pymatbridge.

        log : bool
            Whether to save a log file in some known location.

        maxtime : float
           The maximal time to wait for a response from matlab (optional,
           Default is 10 sec)

        platform : string
           The OS of the machine on which this is running. Per default this
           will be taken from sys.platform.

        startup_options : string
           Command line options to pass to MATLAB. Optional; sensible defaults
           are used if this is not provided.
        """
        if platform is None:
            platform = sys.platform
        if startup_options is None:
            if platform == 'win32':
                startup_options = ' -automation -noFigureWindows'
            else:
                startup_options = ' -nodesktop -nodisplay'
        if log:
            startup_options += ' -logfile ./pymatbridge/logs/matlablog_%s.txt' % id
        super(Matlab, self).__init__(executable, socket_addr, id, log, maxtime,
                                     platform, startup_options)

    def _execute_flag(self):
        return '-r'


class Octave(Session):
    def __init__(self, executable='octave', socket_addr=None,
                 id='python-matlab-bridge', log=False, maxtime=60,
                 platform=None, startup_options=None):
        """
        Initialize this thing.

        Parameters
        ----------

        executable : str
            A string that would start Octave at the terminal. Per default, this
            is set to 'octave', so that you can alias in your bash setup

        socket_addr : str
            A string that represents a valid ZMQ socket address, such as
            "ipc:///tmp/pymatbridge", "tcp://127.0.0.1:55555", etc.

        id : str
            An identifier for this instance of the pymatbridge.

        log : bool
            Whether to save a log file in some known location.

        maxtime : float
           The maximal time to wait for a response from matlab (optional,
           Default is 10 sec)

        platform : string
           The OS of the machine on which this is running. Per default this
           will be taken from sys.platform.

        startup_options : string
           Command line options to pass to Octave. Optional; sensible defaults
           are used if this is not provided.
        """
        if startup_options is None:
            startup_options = '--silent --no-gui'
        super(Octave, self).__init__(executable, socket_addr, id, log, maxtime,
                                     platform, startup_options)

    def _preamble_code(self):
        code = super(Octave, self)._preamble_code()
        if self.log:
            code.append("diary('./pymatbridge/logs/octavelog_%s.txt')" % self.id)
        return code

    def _execute_flag(self):
        return '--eval'
