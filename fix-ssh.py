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
	child.expect (r'\S0.#')
	child.sendline ('show run | i hostname')
	child.expect (r'\S0.#')
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



	child.sendline ('show ip ssh')
	child.expect (prompt)
	child.sendline ('conf t')
	child.expect (config_prompt)
	child.sendline ('ip ssh version 2')
	child.expect (config_prompt)
	child.sendline ('line vty 0 15')
	child.expect (config_line)
	child.sendline ('transport input telnet ssh')
	child.expect (config_line)
	child.sendline ('end')
	child.expect(prompt)
	child.sendline ('wr me')
	child.expect(prompt)
	child.sendline ('show ip ssh')
	child.expect (prompt)
	output_t = child.before.split('\r\n')
	if output_t:
		for i in output_t:
			if i.startswith('SSH'):
				print (HOST + "," + hostname_g.group(1) + "," + i)

	child.sendline ('exit')
	child.expect(pexpect.EOF);
