FROM haproxy:2.7
USER root
RUN apt-get update && \
    apt-get install -y lua5.3 liblua5.3-dev luarocks
RUN luarocks install luasocket && \
    luarocks install lua-cjson
USER haproxy
