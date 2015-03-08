# rpmdistro-gitoverlay

This is a tool to manage an "overlay" of packages on top of a base
distribution, where the upstream sources come from upstream git, and
the spec files are automatically edited.

The output is a yum repository; however, a signature feature is that
the version numbers may go down.  The output RPMs will consistently have
version numbers derived from `git describe`, and the input manifest may
at any point use older commits.

Currently it uses `mockchain` to build.

The code in this project originated from
https://github.com/redhat-openstack/rdopkg as a baseline; however it
is (will become) rather different.

