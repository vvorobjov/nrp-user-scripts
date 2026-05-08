FROM haproxy:3.0

# haproxy 3.0 is on the long-term-support branch. Bumped from 2.7
# (out of LTS) per EBR2-48. Bump again when 3.x LTS rolls.
#
# Lua bumped 5.3 → 5.4 in lockstep; the only 5.3-vs-5.4 surface
# touched by config_files/haproxy/cors.lua is `ipairs`, which is
# behaviour-compatible across the two versions. No `unpack`,
# `module()`, `getfenv`/`setfenv`, `loadstring`, or `table.maxn`.

USER root
# build-essential is required by luarocks (gcc/make) when it
# compiles native components of luasocket and lua-cjson. Removed
# again at the end of the layer to keep the runtime image small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        lua5.4 liblua5.4-dev luarocks build-essential && \
    luarocks --lua-version=5.4 install luasocket && \
    luarocks --lua-version=5.4 install lua-cjson && \
    apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*
USER haproxy
