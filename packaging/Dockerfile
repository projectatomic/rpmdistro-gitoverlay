FROM centos
# We install fedpkg specifically because while it's optional, pretty much everyone
# will want it.
RUN cd /etc/yum.repos.d && \
    yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
    curl -L -O https://copr.fedorainfracloud.org/coprs/walters/buildtools/repo/epel-7/walters-buildtools-epel-7.repo && \
    yum -y install yum-utils && yum-config-manager --enable epel-testing &&  \
    yum -y install \
    	rpmdistro-gitoverlay \
	fedpkg \
    && yum clean all && \
    adduser unprivileged && usermod -a -G mock unprivileged
USER unprivileged
WORKDIR /rdgo
ENTRYPOINT ["rpmdistro-gitoverlay"]


# Usage examples:
#  (Note we need --privileged since mock uses container functions internally)
#  alias rdgo='docker run -ti --rm --privileged -v $(pwd):/rdgo cgwalters/rpmdistro-gitoverlay'
#  rdgo init
#  rdgo resolve --fetch-all -b
