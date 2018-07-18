#!/usr/bin/env python3

import logging
import os
import pexpect
import random
import sys
import time

# DRY RUN SET TO TRUE WONT MAKE CHANGES
dry_run = True

# TACACS YES PUT IT HERE
username = 'testuser'
password = 'testpass'
en_passw = 'testpass'

# first we need a list of the switches(IPs or hostnames) we are actually doing the work on, for
# now this file needs to be PERFECT, no blank lines or spaces before or after
path_to_switch_list_file = '/home/student/Documents/switch_file.txt'
switch_file = open(path_to_switch_list_file,'r')

# heres our list of switches to loop through and do all the things
switch_list = switch_file.read().split('\n')

# i guess we are also just finding switches and respective interface thats that use vlan 80?
# this seems unrelated that is OKAY we just need the list for it outside the main loop :)
vlan_80_switches = []

# the main loop that does all the stuff
for line in switch_list:  
    current_switch = line
    
    if dry_run:
        print('STARTING UP DRY RUN FOR ' + current_switch)
    
    else:
        print('STARTING UP CONFIGURATION CHANGE FOR ' + current_switch)
        print('PAUSING 10 SECONDS TO CANCEL IF THIS IS A MISTAKE(CTRL + C)')
        time.sleep(10)
    
    # you might need to add some ssh options for encryption or hashes that the switches need if they are old
    ssh_context = 'ssh -F /dev/null -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' + username +'@' + current_switch
    
    switch_cli = pexpect.spawnu(ssh_context)  
    print('Attemping to connect to ' + line)
    
    # THIS BLOCK IS TO JUST GET US INTO ENABLE MODE...
    
    ssh_context.expect('assword')
    print('SAW PASSWORD PROMPT, SENDING PASSWORD')
    ssh_context.sendline(password)
    
    ssh_context.expect('>')
    print('SAW OPERATIONAL PROMPT, SENDING EN')
    ssh_context.sendline('en')
    
    ssh_context.expect('assword')
    print('SAW EN PASSWORD PROMPT, SENDING EN PASS')
    ssh_context.sendline(en_passw)
    
    ssh_context.expect('#')
    print('SUCCESSFULLY ENTERED ENABLE MODE.')
    
    
    # set the terminal pager, this is not a config change it only lasts for our own ssh session
    ssh_context.sendline('terminal length 0')
    
    # do the first check 1a-c
    ssh_context.sendline('show run | i dox1x system-auth-control')
    ssh_context.expect('#')
    
    # I DONT KNOW WHAT WE SHOULD LOOK FOR BUT IT SHOULD BE ADDED HERE
    global_config = '?'
    
    # if whatever we are looking for is NOT present, forget this switch and go to the next one...
    if global_config not in ssh_context.before.decode('UTF-8'):
        print('NO GLOBAL CONFIG PRESENT ON ' + current_switch + ' SKIPPING...')
        ssh_context.close()
        continue
    
    # This is the way that I would do it, but can be switched around. since we have a bunch of stuff to check,
    # I guess we can use show int status as a list to loop through, building a second list of ports we want to change
    interfaces_to_change = []
    
    ssh_context.sendline('show int status')
    ssh_context.expect('#')
    print('SENT SHOW INT STATUS')
    
    # now we have a giant string with the output, turn it to a list. Cisco endlines use \r\n on some devices,
    # or only a \n on others, it shouldn't matter though... just in case.
    int_stat_list = ssh_context.before.decode('UTF-8').split('\r\n')
    
    # loop through each line in show int status
    for line in int_stat_list:
        # does the first empty 'space' or line in the output count? I dont know but we can skip it
        if not line.strip():
            continue
        
        # skip column headers
        if 'Status' in line:
            continue
        
        # is this a trunk? then skip.
        if 'trunk' in line:
            print('FOUND TRUNK, SKIPPING THE FOLLOWING INTERFACE.')
            print(line)
            continue
        
        # now time to break up each line to work with it more better
        line_list = line.split()
        
        # if interface is in vlan 30, then skip. i think the vlan should be element 2 in our split line list? test.
        if line_list[2] == '30':
            print('FOUND PORT IN VLAN 30, SKIPPING THE FOLLOWING INTERFACE.')
            print(line)
            continue
        
        if line_list[2] == '80':
            print('FOUND PORT IN VLAN 80, SKIPPING THE FOLLOWING INTERFACE, BUT RECORDING FOR LATER OUTPUT')
            print(line)
            vlan_80_switches.append([current_switch, line_list[0]])
            continue
        
        # if it doesn't fit the skip criteria above, its gonna get the 802.1x changes. record int and vlan pair
        else:
            interfaces_to_change.append([list[0], line_list[2])
                                         
        
    # build the changes we need...
    prepped_changes = ['conf t']
        
    for interface in interfaces_to_change:
        # get a blank line in there between interface changes.
        prepped_changes.append('')
        # interface name
        prepped_changes.append('interface ' + interface[0])
        # rest of garbage
        prepped_changes.append('authentication host-mode multi-domain')
        prepped_changes.append('authentication order dot1x mab')
        prepped_changes.append('authentication priority dot1x mab')
        prepped_changes.append('authentication port-control auto')
        prepped_changes.append('authentication periodic')
        prepped_changes.append('authentication timer reauthenticate server')
        # that line that needs the vlan
        prepped_changes.append('authentication event server dead action authorize vlan ' + interface[2])
        prepped_changes.append('authentication event server dead action authorize voice')
        prepped_changes.append('mab')
        prepped_changes.append('dot1x pae authenticator')
        prepped_changes.append('dot1x timeout server-timeout 30')
        prepped_changes.append('dot1x timeout tx-period 6')
        prepped_changes.append('dot1x max-req 2')
        prepped_changes.append('dot1x max-reauth-req 3')
            
    prepped_changes.append('end')
        
    # need it to be one long string with carriage returns
    final_changes = '\r\n'.join(prepped_changes)
    
    if dry_run:
        print()
        print('DRY RUN MODE ON - HERE ARE THE CHANGES WE WOULD HAVE MADE:')
        print('----------------------------------------------------------')
        print(final_changes)
    
    else:
        print()
        print('MAKING CONFIG CHANGES NOW - STANDBY')
        ssh_context.sendline(final_changes)
        ssh_context.expect('#')
        config_result = ssh_context.before
        
        ssh_context.sendline('end')
        ssh_context.expect('#')
        
        ssh_context.sendline('wr mem')
        ssh_context.expect('#')
        
        ssh_context.sendline('exit')
        ssh_context.close()
        
        print('CONFIG CHANGES COMPLETE, RESULT OF SESSION BELOW - CHECK FOR ERRORS.')
        print(config_result)
        
print()
print('INTERFACES IN VLAN 80 FOUND(BLANK IF NONE)')
print('------------------------------------------')
    
for switch in vlan_80_switches:
    print(switch[0] + ' ' + switch[1])

print('script done.')
