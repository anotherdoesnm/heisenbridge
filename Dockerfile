FROM docker.io/alpine:3.20

# install runtime dependencies
RUN apk add --no-cache python3 py3-ruamel.yaml.clib

WORKDIR /opt/heisenbridge
COPY . .

# install deps and run a sanity check
#
# `python3-dev gcc musl-dev` are installed because building `multidict`
# on armv7l fails otherwise. amd64 and aarch64 don't need this.
#
# `tools/apply_patches.py` applies this fork's changes to the pristine upstream
# sources. It fails loudly when an anchor is gone, so a rebase cannot silently
# produce an unpatched image.
RUN apk add --no-cache --virtual build-dependencies py3-setuptools py3-pip python3-dev gcc musl-dev && \
    python3 tools/apply_patches.py && \
    python setup.py gen_version && \
    rm -rf .git && \
    pip install --break-system-packages -e . && \
    apk del build-dependencies && \
    python -m heisenbridge  -h

# identd also needs to be enabled with --identd in CMD
EXPOSE 9898/tcp 113/tcp
ENTRYPOINT ["heisenbridge", "-l", "0.0.0.0"]
CMD []
