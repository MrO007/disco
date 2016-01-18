

#!/usr/bin/python

# External Libs
import time, datetime
import getpass, paramiko, socket
import sys, re
from ciscoconfparse import CiscoConfParse
import os
from subprocess import Popen

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


def issue_command(username, password, host, command):
    """
        For how to use SSH, google this...
        https://pynet.twb-tech.com/blog/python/paramiko-ssh-part1.html
    """

    remote_conn_pre = paramiko.SSHClient()
    remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Try the SSH but log to our running log when there's a problem

    try:
      # http://yenonn.blogspot.co.uk/2013/10/python-in-action-paramiko-handling-ssh.html
      remote_conn_pre.connect(host, username=username, password=password, allow_agent=False)
    except paramiko.AuthenticationException, e:
      ssh_error = (host + ", Authentication Error: " + str(e) + "\n")
      remote_conn_pre.close()
      return [1, "", "", ssh_error]
    except paramiko.SSHException, e:
      ssh_error = (host + ", SSH Error: " + str(e) + "\n")
      remote_conn_pre.close()
      return [1, "", "", ssh_error]
    except paramiko.BadHostKeyException, e:
      ssh_error = (host + ", BadHostKey: " + str(e) + "\n")
      remote_conn_pre.close()
      return [1, "", "", ssh_error]
    except socket.error, e:
      ssh_error = (host + ", Connection Failed: " + str(e) + "\n")
      return [1, "", "", ssh_error]

    
    transport = remote_conn_pre.get_transport()
    pause = 1  
    ssh_error = ""
    chan = transport.open_session()
    chan.exec_command(command)
    pause = 1
    buff_size = 1024
    stdout = ""
    stderr = ""

    while not chan.exit_status_ready():
        time.sleep(pause)
        if chan.recv_ready():
            stdout += chan.recv(buff_size)

        if chan.recv_stderr_ready():
            stderr += chan.recv_stderr(buff_size)

    exit_status = chan.recv_exit_status()
    # Need to gobble up any remaining output after program terminates...
    while chan.recv_ready():
        stdout += chan.recv(buff_size)

    while chan.recv_stderr_ready():
        stderr += chan.recv_stderr(buff_size)

    return [exit_status, stdout, stderr, ssh_error]

if len(sys.argv) == 1:
    print ("QoS Checker\nCommand Line Usage: [ping/file] [filename]")
    sys.exit()

if sys.argv[1] == "ping":
    # At the moment, ping a pre-defined RS range
    switches = ping_sweep()
elif sys.argv[1] == "file":
    with open(sys.argv[2]) as input_file:
        switches = input_file.read().splitlines()
    input_file.close()

# Get username from user
try:
  username = raw_input("Enter your username: ")
except:
  sys.exit()

# Get password from user (but don't print to screen)
try:
  password = getpass.getpass("Enter your password:")
except:
  sys.exit()

# Create a running log for CSV output of the results - it has no buffer so we can tail -f and follow
filetime_run = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
filename_run = "CDP-log" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("CDP Explorer " + filetime_run + "\n")

last_config_reg = re.compile(r'\!\sLast\sconfiguration\schange\sat\s(.*)\sby\s(.*)')
last_nvram_reg = re.compile(r'\!\sNVRAM\sconfig\slast\supdated\sat\s(.*)\sby\s(.*)')
SERVICEPOLICY_RE = re.compile(r'service-policy\soutput\s(\S+)')

CDP_NEIGHBOR_RE = re.compile(r'Protocol\sinformation\sfor\s(.*)\s:')
CDP_NEIGHBOR_IP_RE = re.compile(r'\s\sIP\saddress:\s(\d+\.\d+\.\d+\.\d+)')

# Loop though our switches
for switch in switches:

    print("Connecting to %s ... " % switch)  
    resp1 = issue_command(username, password, switch, "show run | i hostname")
    if resp1[3]:
        # There's been an error in SSH and we want to log and then continue
        f_run.write (resp1[3])
        continue
    output = resp1[1].split("\r\n")
    
    
    # Write the output to a file
    #filetime = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
    #filename = hostname + "F-" + filetime + ".txt"
    #print ("Writing: %s " % filename)
    #f = open(filename,'a')
    #f.write(output)
    #f.close()


    # Push the "output" thru CiscoConfParse
    # http://www.pennington.net/py/ciscoconfparse/
    parse = CiscoConfParse(output)

    obj_list = []
    obj_list = parse.find_objects(r'hostname')
    if obj_list:
                hostname = obj_list[0].re_match(r'hostname\s(\S+)$')
                print ("Grabbed config from: " + hostname)
    else:
                f_run.write(switch + ",Config grab failed \n")
                continue

    resp1 = issue_command(username, password, switch, "show cdp entry * protocol")
    if resp1[3]:
        # There's been an error in SSH and we want to log and then continue
        f_run.write (resp1[3])
        continue
    output = resp1[1].split("\r\n")

    parse = CiscoConfParse(output)

    neighbors = [obj for obj in parse.find_objects("^Protocol information") if obj.re_search(r"S01") ]
    if neighbors:
        for obj in neighbors:
            neighbor_name = CDP_NEIGHBOR_RE.search (obj.text)
            f_run.write (switch + "," + hostname + "," + neighbor_name.group(1) + "," + obj.re_match_iter_typed(CDP_NEIGHBOR_IP_RE,result_type=str) + "\n")
    else:
        f_run.write (switch + "," + "No CDP Neighbors?\n")
    

f_run.close()



