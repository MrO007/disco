#!/usr/bin/python

import pexpect
import getpass
import re
import sys
import time, datetime
from ciscoconfparse import CiscoConfParse
import iptools

user = raw_input("Enter your remote account: ")
password = getpass.getpass()

if sys.argv[1] == "file":
    with open(sys.argv[2]) as input_file:
        switches = input_file.read().splitlines()
    input_file.close()

# Create a running log for CSV output of the results - it has no buffer so we can tail -f and follow
filetime_run = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
filename_run = "All-Connected" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("All Connected " + filetime_run + "\n")
f_run.write("Site Code,Hostname,Network,NetworkLong,Mask,Interface,Local IP,LocalIPLong\n")

for HOST in switches:
	child = pexpect.spawn ('telnet '+HOST)
	child.expect ('Username: ')
	child.sendline (user)
	child.expect ('Password: ')
	child.sendline (password)
	child.expect (r'\S0.#')
	child.sendline ('show run | i hostname')
	child.expect (r'\S0.#')
	output_t = child.before.split('\r\n')
	if output_t:
		for i in output_t:
			if i.startswith('hostname'):
				hostname_g = re.search('hostname\s(\S+)',i)
				hostname = hostname_g.group(1)
				prompt = (hostname_g.group(1) + "#")
				config_prompt = (hostname_g.group(1) + "\(config\)#") 
				config_line = (hostname_g.group(1) + "\(config-line\)#")
	else: 
		print ("No hostname")
	child.sendline ('term len 0')
	child.expect (prompt)
	child.sendline ('show ip route connected | i ^C')
	child.expect (prompt)
	parse = CiscoConfParse(child.before.split('\r\n'))
	routing_table_entries = [obj for obj in parse.find_objects("^C") if not obj.re_search(r"Loopback") ]
	if not routing_table_entries:
	  f_run.write(switch + "," + hostname + ", no routing table entries\n")
	  child.sendline ('exit')
	  child.expect(pexpect.EOF);
	  continue
	for obj in routing_table_entries:
	  routing_lines = re.search(r'^C\s+(\S+\.\S+\.\S+\.\S+)\/(\S\S)\sis\sdirectly\sconnected,\s(\S+)$',obj.text)
	  child.sendline ('sho run int ' + routing_lines.group(3))
	  child.expect (prompt)
	  parse2 = CiscoConfParse(child.before.split('\r\n'))
	  interface_ip = parse2.find_objects("ip address")
	  if not interface_ip:
		f_run.write(switch + "," + hostname + ", no interface ip, " + routing_lines.group(3) + "\n")
		child.sendline ('exit')
		child.expect(pexpect.EOF);
		continue
	  for obj2 in interface_ip:
	    ip_address = obj2.re_match(r'ip\saddress\s(\S+\.\S+\.\S+\.\S+)\s\S+\.\S+\.\S+\.\S+')
	  if not ip_address:
		f_run.write(switch + "," + hostname + ", no IP\n")
		child.sendline ('exit')
		child.expect(pexpect.EOF);
		continue
	  f_run.write (hostname[:5] + "," + hostname + "," + routing_lines.group(1) + "," + str(iptools.ipv4.ip2long(routing_lines.group(1))) + "," + routing_lines.group(2) + "," + routing_lines.group(3) + "," + ip_address + "," + str(iptools.ipv4.ip2long(ip_address)) + "\n")
	child.sendline ('exit')
	child.expect(pexpect.EOF);
f_run.close()
