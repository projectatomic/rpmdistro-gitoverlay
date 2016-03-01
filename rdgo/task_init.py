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

import os
import json
import argparse
import yaml
import copy

from .utils import log, fatal
from .task import Task
from .git import GitMirror


class TaskInit(Task):
    def run(self, argv):
        parser = argparse.ArgumentParser(description="Initialize an overlay directory")

        opts = parser.parse_args(argv)

        ovlpath = self.workdir + '/overlay.yml'
        if not os.path.isfile(ovlpath):
            fatal("Missing overlay.yml - create one or symlink to one")

        changed = False    
        for dname in ['src']:
            dpath = self.workdir + '/' + dname
            if not os.path.isdir(dpath):
                os.mkdir(dpath)
                changed = True
        if not changed:
            log("This directory appears to already be initialized")
        else:
            log("Initialized src/")
