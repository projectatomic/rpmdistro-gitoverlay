# rpmdistro-gitoverlay

This is a tool to manage an "overlay" of packages on top of a base
distribution, where the upstream sources come from upstream git, and
the spec files are automatically edited.  The output is a single yum
repository.

It is designed to be useful both for developers locally, as well as a
fully automated service.

<hr>

### Differences from COPR

A comparison with http://copr.fedoraproject.org/ is useful.  COPR
could be described as "a web UI on top of mockchain using OpenStack
for builds".  A major difference then is rpmdistro-gitoverlay just
uses raw mock chains - it applies the same security to builds as
regular Koji/Brew does (i.e. build inputs must be fully trusted).

COPR takes SRPMs as input - there are other projects to do the 
`git -> SRPM` stage, whereas rpmdistro-gitoverlay does that internally.

COPR is also a service with both a UI and an API, whereas
rpmdistro-gitoverlay is designed with its sole input to be a YAML
file, stored in a git repository.  It will attempt to synchronize
state to whatever is specified in the YAML file.

For example, if you delete a source from the overlay, all RPMs
generated from that source will also drop out of the generated
repository.  Whereas COPR is a stateful system.

## An example overlay file

    # An example overlay file
    
    aliases: 
      - name: github
        url: git://github.com/
    
      - name: gnome
        url: git://git.gnome.org/
    
      - name: fedorapkgs
        url: git://pkgs.fedoraproject.org/
    
    distgit:
      prefix: fedorapkgs
      branch: master
      
    root:
      mock: fedora-rawhide-x86_64
    
    cache:
      buildserial: 0
    
    components:
      - src: gnome:ostree
    
      - src: github:hughsie/libhif
        freeze: 07fb582c331773ea8ee60513d8ee74f592a7eab9
        distgit: 
          name: libhif
          patches: drop
    
      - src: github:projectatomic/rpm-ostree
        distgit:
          name: rpm-ostree
          patches: drop

## Running

Create a working directory where the primary data `src/` and `rpms/`
will be stored, and copy your `overlay.yml` in there (or symlink it to
a git checkout):

    mkdir -p /srv/build
    ln -s ~walters/src/fedora-atomic/overlay.yml .

Now, we perform a `resolve`: This will generate a `src/` directory
which is a git mirror of all inputs (recursively mirroring
submodules), and take a snapshot of exact commits into `snapshot.json`

    rpmdistro-gitoverlay resolve --fetch-all
    ls -al snapshot.json

Now, let's do a build:

    rpmdistro-gitoverlay build

This will generate `rpms/`, which is a yum repository.  Note however
the system is idempotent, if we run again:

    rpmdistro-gitoverlay build

Nothing should happen aside from a `createrepo` invocation.
    
### Other tools

The code in this project originated from
https://github.com/redhat-openstack/rdopkg as a baseline; however it
is (will become) rather different.

See also https://fedoraproject.org/wiki/Layered_build_scripts_for_package_maintainers
for a collection of other projects.

