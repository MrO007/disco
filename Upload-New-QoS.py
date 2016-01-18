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

def send_ssh_command_get_response (ssh_session, command, prompt):
    response = ""
    response_t = ""
    output = ""
    echo_back = ""
    pause = 1
    now = int(time.time())
    bail_timeout = 60
    timeout = now + bail_timeout
    ssh_session.send(command)
    #while not ssh_session.recv_ready():
    #  time.sleep(pause)
    while not response.endswith(prompt):
        now = int(time.time())
        if ssh_session.recv_ready():
          response += ssh_session.recv(2000)
        else:
            if now == timeout:
                response = "Command time out - wrong prompt?"
                break
            else:
                continue
    response_t = response.lstrip(command)
    return response_t

if len(sys.argv) == 1:
    print ("QoS Uploader\nCommand Line Usage: [file] [filename]")
    sys.exit()

if sys.argv[1] == "file":
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
filename_run = "QoS-Uploader-log" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("QoS Uploader " + filetime_run + "\n")

# Loop though our switches
for switch in switches:

    print("Connecting to %s ... " % switch)  
    resp1 = issue_command(username, password, switch, "show run | i hostname")
    if resp1[3]:
        # There's been an error in SSH and we want to log and then continue
        f_run.write (resp1[3])
        continue
    output = resp1[1].split("\r\n")

    # Push the "output" thru CiscoConfParse
    # http://www.pennington.net/py/ciscoconfparse/
    parse = CiscoConfParse(output)

    obj_list = []
    obj_list = parse.find_objects(r'hostname')
    if obj_list:
                hostname = obj_list[0].re_match(r'hostname\s(\S+)$')
                print ("Connected to: " + hostname)
                exec_prompt = (hostname + "#")
    else:
                f_run.write(switch + ",hostname grab failed \n")
                continue
    
    remote_conn_pre = paramiko.SSHClient()
    remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
      # http://yenonn.blogspot.co.uk/2013/10/python-in-action-paramiko-handling-ssh.html
      remote_conn_pre.connect(switch, username=username, password=password, allow_agent=False)
    except paramiko.AuthenticationException, e:
      f_run.write(switch + ", Authentication Error: " + str(e) + "\n")
      remote_conn_pre.close()
      continue
    except paramiko.SSHException, e:
      f_run.write(switch + ", SSH Error: " + str(e) + "\n")
      remote_conn_pre.close()
      continue
    except paramiko.BadHostKeyException, e:
      f_run.write(switch + ", BadHostKey: " + str(e) + "\n")
      remote_conn_pre.close()
      continue
    except socket.error, e:
      f_run.write(switch + ", Connection Failed: " + str(e) + "\n")
      continue

    remote_conn = remote_conn_pre.invoke_shell()
    send_ssh_command_get_response(remote_conn,"\n",exec_prompt)
    send_ssh_command_get_response(remote_conn,"term len 0\n",exec_prompt)
    send_ssh_command_get_response(remote_conn, "copy ftp://10.6.12.18/GLOBAL-ENHANCED-DATA-ACL.txt running-config\n", "[running-config]? ")
    send_ssh_command_get_response(remote_conn, "\n", exec_prompt)
    send_ssh_command_get_response(remote_conn,"\n",exec_prompt)
    send_ssh_command_get_response(remote_conn, "wr me\n", exec_prompt)
    send_ssh_command_get_response(remote_conn,"\n",exec_prompt)
    new_acl = send_ssh_command_get_response(remote_conn,"show run | s ip access-list extended ENHANCED-DATA\n",exec_prompt)
    acl_output = new_acl.split("\r\n")
    parse = CiscoConfParse(acl_output)
    access_list_process = parse.find_children_w_parents(r"ip access-list extended ENHANCED-DATA",r"remark Version")
    if access_list_process:
        access_list_version = re.sub(r'^ remark ','',access_list_process[0])
    else:
        access_list_version = "No Version Number" 
    print (switch + " " + hostname + " " + access_list_version)
    f_run.write(switch + "," + hostname + "," + access_list_version + "\n")
    remote_conn_pre.close()

f_run.close()



