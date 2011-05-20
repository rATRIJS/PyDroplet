#!/usr/bin/python

import sys
import os
import time

import getopt # used to parse given executable attributes
import inspect # used to inspect currently executed script
import getpass # used to get user password input from terminal window

#import pynotify # notification API for Linx
#import paramiko # enables SSH support in Python
from colorama import Fore, Style # allows to use colours in terminal output

class PyDropletOptionValidator:
    def validate(self, field, value, default):
        value = self.__checkEmpty(field, value, default)

        field = self.__camelcasify(field)

        return getattr(self, 'validate' + field)(value, default)

    def validateServer(self, value, default):
        return value

    def validatePort(self, value, default):
        return value

    def validatePath(self, value, default):
        if(value[0] != '~' and value[0] != '/'):
            raise PyDropletOptionValidatorException('Field `path` must start with either `~` or `/`')

        if(value[-1] != '/'):
            value = value + '/'

        return value

    def validateUsername(self, value, default):
        return value

    def validatePassword(self, value, default):
        return value

    def validateAuthType(self, value, default):
        if(value not in ['credentials', 'key']):
            raise PyDropletOptionValidatorException('Field `path` must be one of these values: [credentials, key].')

        return value

    def validateFile(self, value, default):
        return value

    def __checkEmpty(self, field, value, default):
        if(value == ''):
            if(default == False):
                raise PyDropletOptionValidatorException('Field `%s` myst not be empty' % (field));
            else:
                return default

        return value

    def __camelcasify(self, field):
        field = field.replace('-', '_')

        camel = '';
        for i, part in enumerate(field.split('_')):
            camel += part.capitalize()

        return camel

class PyDropletOptionValidatorException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class PyDroplet:
    actionMap = {
        'create': {
            'method': 'runCreate',
            'options': {
                'path': False,
                'server': False,
                'username': False,
                'password': 1,
                'auth-type': 'credentials',
                'port': 22,
                'file': os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            }
        },
        'scp': {
            'method': 'runScp',
            'options': {
                'file': False,
                'path': False,
                'server': False,
                'username': False,
                'password': 1,
                'auth-type': 'credentials',
                'port': 22
            }
        },
        'interactive': {
            'method': 'runInteractive',
            'options': {}
        }
    }
    
    validator = False
    pynotify = False
    paramiko = False
    action = False
    options = False
    
    def __init__(self, args):
        self.__prepareDependencies()

        self.validator = PyDropletOptionValidator()

        self.parseArgs(args)
    
    def parseArgs(self, args):
        if(len(args) > 0 and args[0] in self.actionMap):
            args.append(args[0])
            args = args[1:]
        
        options, arguments = getopt.getopt(args, 'dps', ['server=', 'path=', 'port=', 'file=', 'username=', 'password=', 'auth-type='])
        
        if(len(arguments) == 0):
            self.action = 'interactive'
        else:
            self.action = arguments[0]
            
        if(self.action not in self.actionMap):
            self.fail('Supplied action is not supported.')
            
        self.prepareOptions(options)
            
    def prepareOptions(self, options):
        self.options = {}
        requiredOptions = self.actionMap[self.action]['options']
        options = dict(options)
        
        for key, value in options.items():
            options[key[2:]] = value
            del options[key]
        
        for key, value in requiredOptions.items():
            if(key not in options):
                if(value == False):
                    self.fail('You must provide ' + key + ' option.')
                else:
                    self.options[key] = value
            else:
                self.options[key] = options[key]
        
    def run(self):
        v = getattr(self, self.actionMap[self.action]['method'])()
        
    def runInteractive(self):
        options = self.actionMap['create']['options']

        self.__userInputOption('server', 'Server host where to send files to', options['server'])
        self.__userInputOption('port', 'Port to connect to (leave blank to default to 22)', options['port'])
        self.__userInputOption('path', 'Directory where to put files on remote server', options['path'])
        self.__userInputOption('username', 'Username to use when connecting to remote server', options['username'])
        self.__userInputOption('auth-type', 'Authentication type(enter `credentials` for username:password authentication or `key` to use your id_rsa key)', options['auth-type'])
        self.__userInputOption('password', 'Password (for either given username to connect to remote server' +
            '(if authentication type is `credentials`) or password to your private id_rsa key ' +
            'if it is encrypted and authentication type is `key`. ' +
            'Set value to 0 if no password is required or to 1 if you would rather input the password on every upload)', options['password'])
        self.__userInputOption('file', 'Where to store the droplet. (leave blank to store in the same directory where this script is)', options['file'])
            
        self.runCreate()
        
    def runCreate(self):
        manifest = "#!/usr/bin/env xdg-open\n\n"
        manifest += "[Desktop Entry]\n"
        manifest += "Version=1.0\n"
        manifest += "Type=Application\n"
        manifest += "Terminal=true\n"
        manifest += "Exec=%s scp --path %s --server %s --username %s --password %s --auth-type %s --port %s --file\n"
        manifest += "Name=PyDroplet-%s\n"
        manifest += "Icon=/\n"
        
        manifest = manifest % (
            os.path.abspath(inspect.getfile(inspect.currentframe())),
            self.options['path'],
            self.options['server'],
            self.options['username'],
            self.options['password'],
            self.options['auth-type'],
            self.options['port'],
            self.options['server']
        )
        
        manifestFile = self.options['file'] + '/PyDroplet-' + self.options['server'] + '.desktop'
        
        with open(manifestFile, 'wb') as f:
            f.write(manifest)
            
        os.chmod(manifestFile, 0777)
        
        print manifest
        print self.options['file']
        
    def runScp(self):
        try:
            password = int(self.options['password'])
        except ValueError:
            password = self.options['password']
            
        if(password == 1):
            text = ''
            if(self.options['auth-type'] == 'key'):
                text = 'You private key password: '
            else:
                text = self.options['username'] + '@' + self.options['server'] + ' password: '
            
            password = getpass.getpass(text)
        else:
            password = str(password)
        
        t = self.paramiko.Transport((self.options['server'], int(self.options['port'])))
        
        if(self.options['auth-type'] == 'credentials'):
            t.connect(username = self.options['username'], password = password)
        elif(self.options['auth-type'] == 'key'):
            if(password == 0):
                key = self.paramiko.RSAKey.from_private_key_file(os.path.expanduser('~/.ssh/id_rsa'))
            else:
                key = self.paramiko.RSAKey.from_private_key_file(os.path.expanduser('~/.ssh/id_rsa'), password)
                
            t.connect(username = self.options['username'], pkey = key)
        else:
            self.fail('Wrong auth-type supplied - valid types are [credentials, key]')
        
        sftp = self.paramiko.SFTPClient.from_transport(t)
        
        sftp.put(self.options['file'], self.options['path'] + os.path.basename(self.options['file']))
        
        sftp.close()
        t.close()
        
        self.notify('File sent.')
        
    def notify(self, message):
        self.pynotify.init('PyDroplet')
        self.pynotify.Notification('PyDroplet', message).show()
    
    def fail(self, reason):
        print reason
        
        sys.exit(0)

    def __userInputOption(self, option, question, default):
        success = False

        while(success is False):
            value = raw_input(question + ': ')

            try:
                value = self.validator.validate(option, value, default)

                print Fore.GREEN + Style.BRIGHT + 'Option `' + option + '` set to value `' + str(value) + '`' + Style.RESET_ALL + Fore.RESET + '\n'
                success = True
            except PyDropletOptionValidatorException as e:
                success = False

                print Fore.RED + Style.BRIGHT + e.value + Style.RESET_ALL + Fore.RESET + '\n'

        self.options[option] = value

    def __prepareDependencies(self):
        import pynotify # notification API for Linux
        import paramiko # enables SSH support in Python

        self.pynotify = pynotify
        self.paramiko = paramiko
        
        
if __name__ == '__main__':
    pd = PyDroplet(sys.argv[1:])
    pd.run()