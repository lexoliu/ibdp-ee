math.randomseed(os.time())


-- FNV-1a 32-bit hash
function fnv1a_hash(x)
  local hash = 2166136261
  local prime = 16777619
  local s = tostring(x)
  for i = 1, #s do
    hash = hash ~ string.byte(s, i)
    hash = (hash * prime) % 2^32
  end
  return tostring(hash)
end

function request()
  local key = fnv1a_hash(math.random(1, 100000))
  return wrk.format("DELETE", "/kv/" .. key)
end
