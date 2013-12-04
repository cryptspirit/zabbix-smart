#!/usr/bin/python2
# coding: utf-8
#       Copyright 2013  Maksim Podlesniy <root at nightbook.info>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
'''Zabbix agent util from S.M.A.R.T monitor.
    Usage:
        smart-stats.py 30 /dev/sda Temperature_Celsius UPDATED megaraid,1
                        |   |       |                   |       |
                        |   |       |                   |       └----------- -d <type> (man smartctl)
                        |   |       |                   └------------------- SMART table header or HEALTH (VALUE - THRESH)
                        |   |       └--------------------------------------- SMART Attributes
                        |   └----------------------------------------------- block device
                        └--------------------------------------------------- cache time to live (TTL in seconds)
        smart-stats.py megacli 0
                        |       |
                        |       └---- LSI MEGARAID array
                        └------------ discovery devices id
'''

from __future__ import print_function
from os import environ, access, X_OK
from os.path import isfile, getmtime, exists
from sys import stderr, argv
from subprocess import Popen, PIPE
from cPickle import loads, dumps
from json import dumps as jdumps
import time

filecache = '/run/shm/zabbix-smart-agent.dumps'
header_match = {
        'FLAG': 2,
        'VALUE': 3,
        'WORST': 4,
        'THRESH': 5,
        'TYPE': 6,
        'UPDATED': 7,
        'WHEN_FAILED': 8,
        'RAW_VALUE': 9,
        }

def get_utils(env_name, default_value):
    '''Check utils
    '''
    if env_name in environ:
        fpath = environ[env_name]
    else:
        fpath = default_value
    if isfile(fpath) and access(fpath, X_OK):
        return fpath
    else:
        print('%s not found or file not executable' % fpath, file=stderr)
        exit(1)

def get_smart_status(disk, types=None):
    smartctl_path = get_utils('smartctl_path', '/usr/sbin/smartctl')
    sudo_path = get_utils('sudo_path', '/usr/bin/sudo')
    cmd = '%s %s' % (sudo_path, smartctl_path)
    if types:
        cmd = '%s -d %s' % (cmd, types)
    cmd = '%s -A %s' % (cmd, disk)
    return Popen(cmd, shell = True, stdout = PIPE).stdout.readlines()

def find_attr(filecache, attr, header):
    '''Find in list data string with attribute values
    '''
    with open(filecache) as f:
        from_pickl = loads(f.read())
    for i in from_pickl:
        if i[1] == attr:
            if header == 'HEALTH':
                return int(i[header_match['VALUE']]) - int(i[header_match['THRESH']])
            else:
                return i[header_match[header]]

def megacli(array):
    '''Discovery device id
    '''
    megacli_path = get_utils('megacli_path', '/usr/sbin/megacli')
    sudo_path = get_utils('sudo_path', '/usr/bin/sudo')
    ret = Popen('%s %s -pdlist -a%s' % (sudo_path, megacli_path, array), shell = True, stdout = PIPE).stdout.readlines()
    ids = {
            'data': [
                ]
            }
    for i in ret:
        if len(i) > 11 and i[:11] == 'Device Id: ':
            ids['data'].append(
                    {
                        '{#ARRAY}': array,
                        '{#DEVICEID}': i[10:-1].strip(),
                        }
                    )
    print(jdumps(ids, sort_keys=True, indent=3, separators=(',', ': ')))

def cachegen(data, filecache):
    '''Create cache
    '''
    ty = False
    to_pickl = []
    for i in data:
        d = i.split()
        if len(d) == 0 and ty:
            break
        elif ty:
            to_pickl.append(d)
        elif len(d) == 10 and d[0] == 'ID#' and d[1] == 'ATTRIBUTE_NAME':
            ty = True
    with open(filecache, 'w') as f:
        f.write(dumps(to_pickl))


def main(ttl, disk, attr, header, types):
    if not exists(filecache) or ((time.time() - getmtime(filecache)) > float(ttl)):
        cachegen(get_smart_status(disk, types), filecache)
    print(find_attr(filecache, attr, header))

if __name__ == '__main__':
    if len(argv) == 1:
        print(__doc__, file=stderr)
        exit(1)
    if len(argv) > 1 and argv[1] == 'megacli':
        if len(argv) > 2:
            array = argv[2]
        else:
            array = 0
        megacli(array)
    else:
        if len(argv) < 5:
            exit(1)
        else:
            if len(argv) > 5:
                types = argv[5]
            else:
                types = None
            main(argv[1], argv[2], argv[3], argv[4], types)
