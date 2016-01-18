

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
filename_run = "QoS-log" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("QoS Explorer " + filetime_run + "\n")

last_config_reg = re.compile(r'\!\sLast\sconfiguration\schange\sat\s(.*)\sby\s(.*)')
last_nvram_reg = re.compile(r'\!\sNVRAM\sconfig\slast\supdated\sat\s(.*)\sby\s(.*)')

# Loop though our switches
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

    # Search the config for Interfaces, QoS and ACLs

    class_map_p = []
    interfaces = [obj for obj in parse.find_objects("^interface") if obj.re_search_children(r"service-policy\soutput\s") ]
    if not interfaces:
        qos_output = (switch + "," + hostname + ",No QoS" + "\n")
        f_run.write(qos_output)
        continue

    last_config_t = []
    last_nvram_t = []
    last_config_t = parse.find_objects(r'! Last configuration change')
    last_nvram_t = parse.find_objects(r'! NVRAM config last updated')
    if last_config_t:
        last_config_t1 = last_config_reg.search(last_config_t[0].text)
        if last_config_t1:
            last_config_time = last_config_t1.group(1)
            last_config_user = last_config_t1.group(2)
        else:
            last_config_time = "Not configured?"
            last_config_user = "Not configured?"
    if last_nvram_t:
        last_nvram_t1 = last_nvram_reg.search(last_nvram_t[0].text)
        if last_nvram_t1:
            last_nvram_time = last_nvram_t1.group(1)
            last_nvram_user = last_nvram_t1.group(2)
        else:
            last_nvram_time = "Not configured?"
            last_nvram_user = "Not configured?"

    # Create a regex that matches service policy but groups the policy-map name
    
    SERVICEPOLICY_RE = re.compile(r'service-policy\soutput\s(\S+)')
    INTERFACE_RE = re.compile(r'^interface\s(\S+)')
    CLASS_MAP_RE = re.compile(r'^class-map\smatch-any\s(\S+)')
    # Loop through the interfaces, looking for service-policy output.
    for intobj in interfaces:
        # if the interface has an output service-policy jump in
        if intobj.re_search_children("service-policy output"):
            # Find the class-map children of the policy-map - line terminated to stop half matches
            class_maps_t = parse.find_children("policy-map " + intobj.re_match_iter_typed(SERVICEPOLICY_RE, result_type=str) + "$")
            # CiscoConfParse helpfully includes the parent config, which we don't need so we remove it.
            class_maps_t.remove ("policy-map " + intobj.re_match_iter_typed(SERVICEPOLICY_RE, result_type=str))
            # If there's only on class-map, it's a parent policy in a hirearchical shaper
            if len(class_maps_t) == 1:
                policy_map_parent = intobj.re_match_iter_typed(SERVICEPOLICY_RE, result_type=str)
                # Find all the children of the parent policy
                policy_map_c = parse.find_all_children("policy-map " + intobj.re_match_iter_typed(SERVICEPOLICY_RE, result_type=str))
                # Step through them looking for the child policy-map name
                for pmap_p_child in policy_map_c:
                    pmap_p_child_policy = re.search(r"service-policy (\S+)", pmap_p_child)
                    if pmap_p_child_policy:
                         # We've found it - set the child policy name
                         child_policy = pmap_p_child_policy.group(1)
                         class_maps_t = []
                         # Get the class maps for the policy-map
                         class_maps_t = parse.find_children(r"policy-map " + pmap_p_child_policy.group(1) + "$")
                         # Remove the parent policy-map config - it's not useful to us
                         class_maps_t.remove ("policy-map " + pmap_p_child_policy.group(1))
            else:
                # We've found more than one class-map so this must be parent policy directly on the interface 
                policy_map_parent = "No Parent"
                # Set the policy name
                child_policy = intobj.re_match_iter_typed(SERVICEPOLICY_RE, result_type=str)
            # Remove the class-default class from the list - it's not useful to us
            class_maps_t.remove (" class class-default")
            # Remove everything but the class-map name from the list
            class_maps = [re.sub(r'^ class ','',s) for s in class_maps_t]
            for class_map_f in class_maps:
                #  Go through the class-maps (that came from the policy-map) and find their config - CiscoConfParse outputs a list so we need add the list string to our new list class_map_p
                class_map_t1 = parse.find_objects (r"^class-map match-a.. " + class_map_f)
                class_map_p.append(class_map_t1[0])
                # Do a list comprehension to search the children of all the class-maps for the ENHANCED-DATA ACL use    
                access_list = [obj for obj in class_map_p if obj.re_search_children(r"match access-group name ENHANCED-DATA") ]
                if access_list:
                    # Write out which class-map uses ENHANCED-DATA
                    matching_class_map = access_list[0].re_match(CLASS_MAP_RE)
                    access_list_process = parse.find_children_w_parents(r"ip access-list extended ENHANCED-DATA",r"remark Version")
                    if access_list_process:
                        access_list_version = re.sub(r'^ remark ','',access_list_process[0])
                    else:
                        access_list_version = "No Version Number" 
                else:
                    # If we don't see it, write that out
                    matching_class_map = "NO ENHANCED-DATA"
                    access_list_version = "No Version Number"
            # Write out to the update file with what we found
            qos_output = (switch + "," + hostname + "," + intobj.re_match(INTERFACE_RE) + "," + policy_map_parent + "," + child_policy + "," + matching_class_map + "," + access_list_version + "," + last_config_time + "," + last_config_user + "," + last_nvram_time + "," + last_nvram_user + "\n")
            f_run.write(qos_output)
        else:
            # Write out when don't find QoS
            qos_output = (switch + "," + hostname + "," + intobj.re_match(INTERFACE_RE) + ",No QoS" + "\n")
            f_run.write(qos_output)
f_run.close()



