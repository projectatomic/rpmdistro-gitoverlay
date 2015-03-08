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

import yaml
import copy

from .utils import fatal
from .task import Task
from .git import GitMirror

class TaskResolve(Task):
    def _expand_one_component(self, component):
        component.src = component.get('src', component.get('dist-git'))
        if component.src is None:
            fatal("Component {0} is missing 'src' or 'dist-git'")
        component['dist-git'] = component.get('dist-git', component.src)
        if not component.tag:
            component.branch = component.get('branch', 'master')

    def run(self):
        mirror = GitMirror('/home/walters/tmp/gitmirror')
        with open('overlay.yml') as f:
            overlay = yaml.load(f)
        expanded = copy.deepcopy(overlay)
        for component in expanded:
            self._expand_one_component(component)
            mirror.mirror(component.src, component.branch or component.tag,
                          fetch=True)

        
