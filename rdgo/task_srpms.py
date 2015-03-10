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

import os
import json
import StringIO
import yaml
import tempfile
import copy

from .swappeddir import SwappedDirectory
from .utils import log, fatal, rmrf, ensure_clean_dir, run_sync
from .task import Task
from . import specfile 
from .git import GitMirror

def require_key(conf, key):
    try:
        return conf[key]
    except KeyError, e:
        fatal("Missing config key {0}".format(key))

class TaskSRPMs(Task):

    def run(self):
        snapshot = self.get_snapshot()

        self.srpmdir = SwappedDirectory(self.workdir + '/srpms')
        self.mirror = GitMirror(self.workdir + '/src')
            
