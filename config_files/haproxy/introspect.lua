local http = require("socket.http")
local json = require("json")

local cache = {}
local cache_ttl = 300 -- Time to live for cache entries in seconds

function introspect_token(txn)
    local auth_header = txn.http:req_get_headers()['Authorization']
    if not auth_header then
        txn.http:res_set_status(401)
        txn.http:res_send("Missing Authorization header")
        return
    end
    
    local token = auth_header:match("^Bearer%s+(.+)")
    if not token then
        txn.http:res_set_status(401)
        txn.http:res_send("Invalid Authorization header format")
        return
    end
    
    local cached_entry = cache[token]
    if cached_entry and os.time() < cached_entry.expiry then
        if not cached_entry.is_active then
            txn.http:res_set_status(401)
            txn.http:res_send("Invalid or expired token")
        end
        return
    end
    
    local client_id = "nrp-proxy"
    local client_secret = "EFco68t3e2bwO2i3IBGf4s7UKQEhL+tf"
    local introspection_endpoint = "https://iam-int.ebrains.eu/auth/realms/hbp/protocol/openid-connect/token/introspect"
    local payload = "token=" .. token .. "&client_id=" .. client_id .. "&client_secret=" .. client_secret
    
    local response = http.request("POST", introspection_endpoint, payload)
    local result = json.decode(response)
    
    cache[token] = {
        is_active = result.active,
        expiry = os.time() + cache_ttl
    }

    if result.active ~= true then
        txn.http:res_set_status(401)
        txn.http:res_send("Invalid or expired token")
        return
    end
end
