FROM centos
# We install fedpkg specifically because while it's optional, pretty much everyone
# will want it.
RUN cd /etc/yum.repos.d && \
    yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
    curl -L -O https://copr.fedorainfracloud.org/coprs/walters/buildtools/repo/epel-7/walters-buildtools-epel-7.repo && \
    curl -L -O https://copr.fedorainfracloud.org/coprs/walters/mock/repo/epel-7/walters-mock-epel-7.repo && \
    yum -y install \
    	rpmdistro-gitoverlay \
	fedpkg \
    && yum clean all && \
    adduser unprivileged && usermod -a -G mock unprivileged
USER unprivileged
WORKDIR /srv
ENTRYPOINT ["rpmdistro-gitoverlay"]


# Usage examples:
#  (Note we need --privileged since mock uses container functions internally)
#  alias rdgo='docker run -ti --rm --privileged -v /path/to/rdgo/:/srv cgwalters/rpmdistro-gitoverlay'
#  rdgo init
#  rdgo resolve --fetch-all -b
