#! /usr/bin/env python
'''
Created on September 12, 2014
@author: cwulfman
'''

import os
import re
import argparse

xslpath = '/Users/cwulfman/BlueMountain/util/xsl/metsalto2tei.xsl'
targetroot = '/tmp'

def gen_eggs(sourcedir):
    "Generate simple file to pass to saxon for further processing."
    for root, dirs, files in os.walk(sourcedir):
        print "<book voyagerid='%s'>" % root.split('/')[-1]
        for fname in sorted(files):
            print "<page name='%s' />" % fname
        
        print "</book>"

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_dir", help="top-level directory book jp2s")
    args = parser.parse_args()

    if args.input_dir:
        gen_eggs(args.input_dir)


