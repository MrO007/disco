

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

# Ping sweep the router loopback range to discover the live ones

switches = [] # routers array
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

#switches = ["10.255.254.41"]

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

# Loop though our switches
for switch in switches:

    """
        For how to use SSH, google this...
        https://pynet.twb-tech.com/blog/python/paramiko-ssh-part1.html
    """
    remote_conn_pre = paramiko.SSHClient()
    remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("Connecting to %s ... " % switch)

    # Try the SSH but log to our running log when there's a problem

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
    
    # The first output is the banner
    output = remote_conn.recv(1000)

    
    # Set terminal length and clear the output.
    remote_conn.send("terminal length 0\n")
    time.sleep(0.5)
    output = remote_conn.recv(1000)
    output = ''

    
    # Find the hostname (needed later)
    remote_conn.send("show run | inc hostname \n")
    while not "#" in output:
        # update receive buffer
            output += remote_conn.recv(1024)

    hostname = ''
    for subline in output.splitlines():
        thisrow = subline.split()
        try:
            gotdata = thisrow[1]
            if thisrow[0] == "hostname":
                hostname = thisrow[1]
                prompt = hostname + "#"
        except IndexError:
            gotdata = 'null'


    if not hostname:
           f_run.write(switch + "No Hostname Discovered" + "\n")
           print ("NO HOSTNAME" + output)
    else:
           print ("Connected to: " + hostname)
           
    # Start with empty output & enable loop variable
    output = ''
    keeplooping = True

    # Regex for to find the hostname in a string
    regex = '^' + hostname + '(.*)(\ )?#'
    theprompt = re.compile(regex)

    # Time when the command started, prepare for timeout.
    now = int(time.time())
    bail_timeout = 60
    timeout = now + bail_timeout

    # Send the command
    command = "show run"
    remote_conn.send(command + "\n")

    # loop the output
    while keeplooping:

      # Setup bail timer
      now = int(time.time())
      if now == timeout:
        print "\n Command \"" + command + "\" took " + str(bail_timeout) + "secs to run, bailing!"
        output += "bailed on command: " + command
        keeplooping = False
        break

      # update receive buffer whilst waiting for the prompt to come back
      output += remote_conn.recv(2048)

      # Search the output for our prompt/hostname
      theoutput = output.splitlines()
      for lines in theoutput:
        myregmatch = theprompt.search(lines)

        # If found, exit the loop
        if myregmatch:
          keeplooping = False

    # Write the output to a file
    filetime = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
    filename = hostname + "F-" + filetime + ".txt"
    #print ("Writing: %s " % filename)
    f = open(filename,'a')
    f.write(output)
    f.close()

    remote_conn_pre.close()

    # Push the "output" thru CiscoConfParse
    # http://www.pennington.net/py/ciscoconfparse/
    parse = CiscoConfParse(filename)

    # Search the config for Interfaces, QoS and ACLs

    class_map_p = []
    interfaces = [obj for obj in parse.find_objects("^interface") if obj.re_search_children(r"service-policy\soutput\s") ]

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
            qos_output = (switch + "," + hostname + "," + intobj.re_match(INTERFACE_RE) + "," + policy_map_parent + "," + child_policy + "," + matching_class_map + "," + access_list_version +  "\n")
            f_run.write(qos_output)
	else:
            # Write out when don't find QoS
            qos_output = (switch + "," + hostname + ",No QoS" + "\n")
            f_run.write(qos_output)
f_run.close()



