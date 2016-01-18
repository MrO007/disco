#!/usr/bin/python

# External Libs
import time, datetime
import getpass, paramiko, socket
import sys, re
import iptools
from ciscoconfparse import CiscoConfParse
import os
import glob
from subprocess import Popen
import pandas

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

paramiko.util.log_to_file("paramiko.log")

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
        before_response = len(response)
        now = int(time.time())
        if ssh_session.recv_ready():
          response += ssh_session.recv(9999)
        else:
            if now == timeout:
                response = "Command time out - wrong prompt?"
                break
            else:
                continue
        if len(response) > before_response:
          timeout = now + bail_timeout
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




newest = max(glob.iglob('IOS-and-hash*.txt'), key=os.path.getctime)
if newest:
    with open(newest) as input_file:
        already_done = input_file.read().splitlines()
    input_file.close()

# Create a running log for CSV output of the results - it has no buffer so we can tail -f and follow
filetime_run = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
filename_run = "IOS-and-hash" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("Site Code,Hostname,IP,IOS,IOS file,current hash\n")


colnames = ['Site_Code','Hostname','IP','IOS','IOS_file','current_hash']
ios_hash_existing_data = pandas.DataFrame()
for file in glob.glob("IOS-and-hash*.txt"):
    new_file_data = pandas.read_csv(file, names=colnames, header=0)
    ios_hash_existing_data = ios_hash_existing_data.append(new_file_data, ignore_index=True)


IPs = list(ios_hash_existing_data.IP)

# Loop though our switches
for switch in switches:
    if switch in IPs:
      print (switch + ": Device already passed skipping")
      continue

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
    send_ssh_command_get_response(remote_conn,"term len 0\n","term len 0\r\n" + exec_prompt)


    current_system_image = send_ssh_command_get_response(remote_conn,"sho ver | i System image file is\n",exec_prompt)
    if not current_system_image:
      f_run.write(hostname[:5] + "," + hostname + "," + switch + ", System image not returned\n")
      remote_conn_pre.close()
      continue
    file_location_t = re.search(r'System image file is "(\S+)"',current_system_image)
    file_location = file_location_t.group(1)
    file_path, file_name = os.path.split(file_location)
    verify_image_t = send_ssh_command_get_response(remote_conn,"verify /md5 " + file_location + "\n",exec_prompt)
    if not verify_image_t:
      f_run.write(hostname[:5] + "," + hostname + "," + switch + ", Verify not returned\n")
      remote_conn_pre.close()
      continue
    verify_image_output = verify_image_t.split('\r\n')
    foundit = 0
    for obj in verify_image_output:
      if re.search(r'verify /md5.* \= .*',obj):
        image_hash_g = re.search(r'verify /md5.* \= (.*)',obj)
        print image_hash_g.group(1)
        f_run.write(hostname[:5] + "," + hostname + "," + switch + "," + file_name + "," + file_location + "," + image_hash_g.group(1) + "\n")
        remote_conn_pre.close()
        foundit = 1
        continue
    if not foundit:
      f_run.write(hostname[:5] + "," + hostname + "," + switch + "," + file_name + "," + file_location + ",no hash\n")
      remote_conn_pre.close()
      
f_run.close()



