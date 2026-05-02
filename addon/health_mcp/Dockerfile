ARG BUILD_FROM
FROM $BUILD_FROM

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv

RUN python3 -m venv "$VIRTUAL_ENV"

WORKDIR /usr/src/app

COPY app/ /usr/src/app/
RUN "$VIRTUAL_ENV/bin/pip" install --no-cache-dir .

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
