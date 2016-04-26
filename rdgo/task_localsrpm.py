# Copyright (C) 2016 Colin Walters <walters@verbum.org>
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
import StringIO
import subprocess
import errno
import shutil
import tempfile

from .utils import log, fatal, ensuredir, rmrf, ensure_clean_dir, run_sync
from .basetask_resolve import BaseTaskResolve
from . import specfile 
from .git import GitRemote

class TaskLocalBuildOne(BaseTaskResolve):
    def __init__(self):
        BaseTaskResolve.__init__(self)

    def _run_with_tmp(self, opts, tmpdir):

        gitrev=subprocess.check_output(['git', 'describe', '--always', '--tags'])
        vre = re.compile('^v')
        gitrev_for_pkg=vre.sub('', gitrev.replace('-', '.'))

        srcdir = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'])
        
        spec = self._find_spec('.')
        name = spec.get_tag('Name')
        name_ver = name + '-' + gitrev_for_pkg

        tarfile_tmp_path = tmpdir + '/' + name
        with open(tarfile_tmp_path, 'w') as tarfile_tmp:
            subprocess.check_call(['git', 'archive', '--format=tar',
                                   '--prefix=' + name_ver],
                                  stdout=tarfile_tmp,
                                  cwd=srcdir)
            for line in StringIO.StringIO(subprocess.check_output(['git', 'submodule', 'status'])):
            subprocess.check_call(['git', 'archive', '--format=tar',
                                   '--prefix=' + name_ver],
                                  stdout=tarfile_tmp,
                                  cwd=srcdir)
            

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Build one RPM from local git")

        opts = parser.parse_args(argv)

        tmpdir = tempfile.mkdtemp('', 'rdgo-srpms', self.tmpdir)
        try:

        finally:
            if 'PRESERVE_TEMP' not in os.environ:
                rmrf(tmpdir)
