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

### Other tools

The code in this project originated from
https://github.com/redhat-openstack/rdopkg as a baseline; however it
is (will become) rather different.

See also https://fedoraproject.org/wiki/Layered_build_scripts_for_package_maintainers
for a collection of other projects.

