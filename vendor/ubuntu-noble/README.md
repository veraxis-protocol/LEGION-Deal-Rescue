# Ubuntu 24.04 amd64 CI dependency

The checked-in package is the Ubuntu Noble updates/security binary for bubblewrap
0.9.0-1ubuntu0.3. Its SHA-256 matches the package index authenticated by Ubuntu
APT. The package and source are published in the official Ubuntu archive.

- Binary: https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.9.0-1ubuntu0.3_amd64.deb
- Source package: https://launchpad.net/ubuntu/+source/bubblewrap/0.9.0-1ubuntu0.3

CI verifies SHA-256 before installing the package. The Ubuntu runner image
supplies util-linux/prlimit. The smoke test requires unprivileged sandbox execution.
