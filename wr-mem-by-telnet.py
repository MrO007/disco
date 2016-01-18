import pexpect
import getpass
import re
import sys


user = raw_input("Enter your remote account: ")
password = getpass.getpass()

if sys.argv[1] == "file":
    with open(sys.argv[2]) as input_file:
        switches = input_file.read().splitlines()
    input_file.close()

for HOST in switches:
	child = pexpect.spawn ('telnet '+HOST)
	child.expect ('Username: ')
	child.sendline (user)
	child.expect ('Password: ')
	child.sendline (password)
	child.expect ('S01#')
	child.sendline ('show run | i hostname')
	child.expect ('S01#')
	output_t = child.before.split('\r\n')
	if output_t:
		for i in output_t:
			if i.startswith('hostname'):
				hostname_g = re.search('hostname\s(\S+)',i)
				prompt = (hostname_g.group(1) + "#")
				config_prompt = (hostname_g.group(1) + "\(config\)#") 
				config_line = (hostname_g.group(1) + "\(config-line\)#")
	else: 
		print ("No hostname")




	child.sendline ('wr mem')
	child.expect (prompt)
	output_t = child.before.split('\r\n')
	if output_t:
		for i in output_t:
			if i.startswith('SSH'):
				print (HOST + "," + hostname_g.group(1) + "," + i)

	child.sendline ('exit')
	child.expect(pexpect.EOF);
