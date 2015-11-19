#!/usr/bin/env python
#
# Copyright (C) 2015 Colin Walters <walters@verbum.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import sys
import errno
import subprocess
import os

from .utils import ensuredir, ensure_clean_dir, rmrf

class SwappedDirectory(object):
    def __init__(self, path):
        self.path = path
        self.dn = os.path.dirname(self.path)
        self.bn = os.path.basename(self.path)
        self._version = 0
    
    def read(self):
        if not os.path.islink(self.path):
            subname = '{0}-{1}'.format(self.bn, self._version)
            ensuredir(self.dn + '/' + subname)
            os.symlink(subname, self.path)
        else:
            version = os.readlink(self.path)
            if version.endswith('-0'):
                self._version = 0
            elif version.endswith('-1'):
                self._version = 1
            else:
                raise ValueError("Swapped directory link invalid: {0}".format(version))

    def _newver(self):
        return 1 if self._version == 0 else 0

    def _newdir(self):
        return '{0}-{1}'.format(self.bn, self._newver())

    def _newpath(self):
        return self.dn + '/' + self._newdir()
            
    def prepare(self, save_partial_dir=None):
        self.read()
        newpath = self._newpath()
        if save_partial_dir is not None:
            try:
                stbuf = os.stat(newpath)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
                stbuf = None
            if stbuf is not None:
                rmrf(save_partial_dir)
                os.rename(newpath, save_partial_dir)
        ensure_clean_dir(newpath)
        return newpath

    def abandon(self):
        newpath = self._newpath()
        rmrf(newpath)

    def commit(self):
        newpath = self._newpath()
        tmplink = newpath + '/' + '__tmplink'
        rmrf(tmplink)
        os.symlink(self._newdir(), tmplink)
        os.rename(tmplink, self.path)
        
        
        
            
        
