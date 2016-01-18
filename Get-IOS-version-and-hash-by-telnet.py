#!/usr/bin/python

import pexpect
import getpass
import re
import sys
import time, datetime
from ciscoconfparse import CiscoConfParse
import iptools
import os

user = raw_input("Enter your remote account: ")
password = getpass.getpass()

if sys.argv[1] == "file":
	with open(sys.argv[2]) as input_file:
		switches = input_file.read().splitlines()
	input_file.close()


# Create a running log for CSV output of the results - it has no buffer so we can tail -f and follow
filetime_run = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
filename_run = "IOS-and-hash" + "-" + filetime_run + ".txt"  
f_run = open(filename_run,'a',0)
f_run.write("Site Code,Hostname,IP,IOS,IOS file,current hash\n")

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
	
	child.sendline('sho ver | i System image file is')
	child.expect (prompt)
	current_system_image = child.before
	if not current_system_image:
	  f_run.write(hostname[:5] + "," + hostname + "," + HOST + ", System image not returned\n")
	  child.sendline ('exit')
	  child.expect(pexpect.EOF);
	  continue
	file_location_t = re.search(r'System image file is "(\S+)"',current_system_image)
	file_location = file_location_t.group(1)
	file_path, file_name = os.path.split(file_location)
	child.sendline("verify /md5 " + file_location)
	child.expect (prompt,timeout=300)
	verify_image_t = child.before
	if not verify_image_t:
	  f_run.write(hostname[:5] + "," + hostname + "," + HOST + ", Verify not returned\n")
	  child.sendline ('exit')
	  child.expect(pexpect.EOF);
	  continue
	verify_image_output = verify_image_t.split('\r\n')
	foundit = 0
	for obj in verify_image_output:
	  if re.search(r'verify /md5.* \= .*',obj):
		image_hash_g = re.search(r'verify /md5.* \= (.*)',obj)
		print image_hash_g.group(1)
		f_run.write(hostname[:5] + "," + hostname + "," + HOST + "," + file_name + "," + file_location + "," + image_hash_g.group(1) + "\n")
		child.sendline ('exit')
		child.expect(pexpect.EOF);
		foundit = 1
		continue
	if not foundit:
	  f_run.write(hostname[:5] + "," + hostname + "," + HOST + "," + file_name + "," + file_location + ",no hash\n")
	child.sendline('exit')
	child.expect(pexpect.EOF);
f_run.close()
