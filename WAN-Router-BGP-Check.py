

#!/usr/bin/python

# External Libs
import time, datetime
import getpass, paramiko, socket
import sys, re
import iptools
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


# Ping sweep the router loopback range to discover the live ones
def ping_sweep():
    switches = []
    p = {} # ip -> process
    for n in range(252,255): # start ping processes
        for j in range (256):
                ip = "10.255.%d.%d" % (n,j)
                p[ip] = Popen(['ping', '-n', '-w5', '-c3', ip], stdout=DEVNULL)
        #NOTE: you could set stderr=subprocess.STDOUT to ignore stderr also

    while p:
        for ip, proc in p.items():
            if proc.poll() is not None: # ping finished
                del p[ip] # remove from the process list
                if proc.returncode == 0:
                    switches.append(ip)
                break
    return switches


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
filename_run = "BGP-log" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("BGP Explorer " + filetime_run + "\n")

# Loop though our switches

bgp_reg_ex = re.compile(r'network\s(\d+\.\d+\.\d+\.\d+)\smask\s(\d+\.\d+\.\d+\.\d+)')

for switch in switches:

    print("Connecting to %s ... " % switch)  
    resp1 = issue_command(username, password, switch, "show run")
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

    router_bgp = parse.find_all_children(r'router\sbgp\s\d+$')
    if router_bgp:
        bgp_as_grab = re.search(r"router\sbgp\s(\d+)", router_bgp[0])
        bgp_as = bgp_as_grab.group(1)
        for line in router_bgp:
            network_line = bgp_reg_ex.search(line)
            if network_line:
                f_run.write(switch + "," + hostname + "," + bgp_as + "," + network_line.group(1) + "," + network_line.group(2) + "," + str(iptools.ipv4.ip2long(network_line.group(1))) + "," + str(iptools.ipv4.netmask2prefix(network_line.group(2))) + "\n")
    else:
        f_run.write(switch + "," + "No BGP found?")

    
    #f_run.write(kdkdkdkdk)
f_run.close()



