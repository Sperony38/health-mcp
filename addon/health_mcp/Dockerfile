ARG BUILD_FROM
FROM $BUILD_FROM

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /usr/src/app

COPY app/ /usr/src/app/
RUN pip install --no-cache-dir .

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

